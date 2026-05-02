"""Browser Agent - AI-controlled browser automation with stealth"""
import asyncio
import itertools
import os
import json
import base64
import random
import time
import logging
from functools import partial
from typing import AsyncGenerator, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from proxy_manager import ProxyManager
from action_history import ActionHistory
from captcha_solver import (
    solve_captcha,
    detect_site_key,
    TYPE_HCAPTCHA, TYPE_RECAPTCHA_V2, TYPE_RECAPTCHA_V3,
    TYPE_TURNSTILE, TYPE_CLOUDflare,
)
# T023: TLS fingerprint injection
from tls_inject import TLSInject, merge_fingerprint_headers
# T024: Enhanced JS spoofing + headless bypass
from stealth_enhanced import HEADLESS_DETECTION_BYPASS, build_headless_bypass_headers
# T030: Route interception for challenge detection
from route_interceptor import RouteInterceptor, ChallengeType
# T036: nodriver stealth browser + Playwright CDP bridge
from nodriver_bridge import NodriverBridge
# T031: Site-specific antibot bypass patterns
from site_overrides import match_domain, apply_site_override, get_override_for_url

logger = logging.getLogger(__name__)

# ── Realistic screen/profile pools ─────────────────────────────────────────
_SCREEN_SIZES = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 2560, "height": 1440},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 800},
]

_PROFILES = [
    {"locale": "en-US", "timezone_id": "America/New_York",   "os": "windows"},
    {"locale": "en-US", "timezone_id": "America/Chicago",    "os": "windows"},
    {"locale": "en-US", "timezone_id": "America/Los_Angeles","os": "macos"},
    {"locale": "en-GB", "timezone_id": "Europe/London",      "os": "windows"},
    {"locale": "en-AU", "timezone_id": "Australia/Sydney",   "os": "macos"},
    {"locale": "en-CA", "timezone_id": "America/Toronto",    "os": "windows"},
]

# Stealth Chrome launch args (Chromium fallback only)
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
    "--start-maximized",
    "--disable-infobars",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--no-first-run",
    "--no-service-autorun",
    "--password-store=basic",
    "--use-mock-keychain",
    "--disable-default-apps",
    "--disable-component-update",
    "--no-default-browser-check",
    "--disable-extensions",
    "--mute-audio",
    "--disable-gpu",
    "--lang=en-US,en",
    "--disable-ipc-flooding-protection",
    "--metrics-recording-only",
    "--disable-hang-monitor",
    "--disable-prompt-on-repost",
    "--disable-sync",
]

# Realistic Chrome user agents (used only for Chromium fallback)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.7049.115 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
]

STEALTH_JS = """
(function() {
  // ─── Erase all automation / Playwright / Selenium / CDP traces ───────────
  const _rm = (obj, ...keys) => keys.forEach(k => { try { delete obj[k]; } catch(_) {} });
  _rm(window,
    '__playwright','__pw_manual','_playwrightCommandCounts','__playwright_evaluation_script',
    '__playwright__','__pw_clock',
    'cdc_adoQpoasnfa76pfcZLmcfl_Array','cdc_adoQpoasnfa76pfcZLmcfl_Promise',
    'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
    '__webdriver_evaluate','__selenium_evaluate','__webdriver_script_function',
    '__webdriver_script_func','__webdriver_script_atoms','_selenium',
    '__selenium_unwrapped','__webdriver_unwrapped','__fxdriver_evaluate',
    '__fxdriver_unwrapped','fxdriver_id','cachedFramebot'
  );

  // ─── WebRTC leak blocking ────────────────────────────────────────────────
  // Block all WebRTC ICE candidates from leaking local IP
  if (typeof RTCPeerConnection !== 'undefined') {
    const _origRTC = RTCPeerConnection.bind(RTCPeerConnection);
    RTCPeerConnection = function(pcConfig, pcConstraints) {
      const pc = new _origRTC(pcConfig, pcConstraints);
      const _origAddIceCandidate = pc.addIceCandidate.bind(pc);
      pc.addIceCandidate = function(candidate) {
        // Drop any candidates that expose the real local IP
        if (candidate && candidate.candidate &&
            (candidate.candidate.includes('host') || candidate.candidate.includes('srflx'))) {
          return Promise.resolve();
        }
        return _origAddIceCandidate(candidate);
      };
      const _origCreateOffer = pc.createOffer.bind(pc);
      pc.createOffer = function() {
        return _origCreateOffer().then(offer => {
          // Strip m= lines that expose internal candidates in SDP
          const sdp = offer.sdp.replace(/a=candidate:[^\r\n]+(host|srflx)[^\r\n]+/g, '');
          return Object.assign(offer, { sdp });
        });
      };
      return pc;
    };
    // Expose the original constructor for legitimate use
    window.RTCPeerConnection = RTCPeerConnection;
    window.webkitRTCPeerConnection = window.RTCPeerConnection;
    window.mozRTCPeerConnection = window.RTCPeerConnection;
  }

  // ─── WebRTC getUserMedia — fake camera/mic to avoid permission prompts exposing hardware ─
  if (typeof navigator.mediaDevices !== 'undefined') {
    const _origGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = function(constraints) {
      // Return a silent audio + blank video track to avoid hardware enumeration
      const fakeStream = {
        getAudioTracks: () => [],
        getVideoTracks: () => [{
          kind: 'video',
          label: 'Camera',
          enabled: false,
          on: () => {}, off: () => {},
          addEventListener: () => {}, removeEventListener: () => {},
        }],
        getTracks: () => [],
        active: false,
        addEventListener: () => {}, removeEventListener: () => {},
      };
      return Promise.resolve(fakeStream);
    };
  }

  // ─── WebRTC getDisplayMedia — block screen capture by default ─────────────
  if (typeof navigator.mediaDevices !== 'undefined' && navigator.mediaDevices.getDisplayMedia) {
    const _origGSMedia = navigator.mediaDevices.getDisplayMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getDisplayMedia = function() {
      // Redirect to getUserMedia fake stream instead of real screen capture
      const fakeDisplay = {
        getVideoTracks: () => [{
          kind: 'video', label: 'Screen Capture', enabled: false,
          on: () => {}, off: () => {},
          addEventListener: () => {}, removeEventListener: () => {},
        }],
        getAudioTracks: () => [],
        getTracks: () => [],
        active: false,
        addEventListener: () => {}, removeEventListener: () => {},
      };
      return Promise.resolve(fakeDisplay);
    };
  }
  // Seal against re-injection
  ['__webdriver','__selenium','__webdriver__','__selenium__','__driver_evaluate',
   '__webdriver_evaluate','__fxdriver_evaluate'].forEach(p => {
    try { Object.defineProperty(window, p, { get: () => undefined, configurable: false }); } catch(_) {}
  });

  // ─── navigator.webdriver ─────────────────────────────────────────────────
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
  } catch(_) {}

  // ─── Window dimensions (set per-session from Python to include jitter) ──
  // NOTE: outerWidth/outerHeight are injected dynamically per-session above STEALTH_JS.
  // See _init_browser where add_init_script appends: Object.defineProperty(window,'outerWidth',  {get:()=>vp_w})
  try { Object.defineProperty(window, 'screenX', { get: () => 0 }); } catch(_) {}
  try { Object.defineProperty(window, 'screenY', { get: () => 0 }); } catch(_) {}

  // ─── Screen dimensions ───────────────────────────────────────────────────
  try { Object.defineProperty(screen, 'availWidth',  { get: () => screen.width }); } catch(_) {}
  try { Object.defineProperty(screen, 'availHeight', { get: () => screen.height - 40 }); } catch(_) {}
  try { Object.defineProperty(screen, 'availLeft',   { get: () => 0 }); } catch(_) {}
  try { Object.defineProperty(screen, 'availTop',    { get: () => 0 }); } catch(_) {}
  try { Object.defineProperty(screen, 'colorDepth',  { get: () => 24 }); } catch(_) {}
  try { Object.defineProperty(screen, 'pixelDepth',  { get: () => 24 }); } catch(_) {}

  // ─── navigator properties ─────────────────────────────────────────────────
  try { Object.defineProperty(navigator, 'vendor',              { get: () => 'Google Inc.' }); } catch(_) {}
  try { Object.defineProperty(navigator, 'platform',            { get: () => 'Win32' }); } catch(_) {}
  try { Object.defineProperty(navigator, 'languages',           { get: () => ['en-US', 'en'] }); } catch(_) {}
  try { Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 }); } catch(_) {}
  try { Object.defineProperty(navigator, 'deviceMemory',        { get: () => 8 }); } catch(_) {}
  try { Object.defineProperty(navigator, 'maxTouchPoints',      { get: () => 0 }); } catch(_) {}
  try { Object.defineProperty(navigator, 'doNotTrack',          { get: () => null }); } catch(_) {}
  try { Object.defineProperty(navigator, 'cookieEnabled',       { get: () => true }); } catch(_) {}

  // ─── navigator.connection ────────────────────────────────────────────────
  const _conn = { effectiveType: '4g', downlink: 8.9, rtt: 48, saveData: false,
    type: 'wifi', onchange: null, addEventListener: () => {}, removeEventListener: () => {} };
  try { Object.defineProperty(navigator, 'connection',       { get: () => _conn }); } catch(_) {}
  try { Object.defineProperty(navigator, 'mozConnection',    { get: () => undefined }); } catch(_) {}
  try { Object.defineProperty(navigator, 'webkitConnection', { get: () => undefined }); } catch(_) {}

  // ─── Battery API ─────────────────────────────────────────────────────────
  if (!navigator.getBattery) {
    navigator.getBattery = () => Promise.resolve({
      charging: true, chargingTime: 0, dischargingTime: Infinity,
      level: 0.88 + Math.random() * 0.12,
      addEventListener: () => {}, removeEventListener: () => {}
    });
  }

  // ─── Plugins — real Chrome has exactly these three ───────────────────────
  const _pd = [
    { name:'Chrome PDF Plugin',  filename:'internal-pdf-viewer', description:'Portable Document Format' },
    { name:'Chrome PDF Viewer',  filename:'mhjfbmdgcfjbbpaeojofohoefgiehjai', description:'' },
    { name:'Native Client',      filename:'internal-nacl-plugin', description:'' },
  ];
  const _pl = Object.assign([], {
    item:      i    => _pd[i] || null,
    namedItem: name => _pd.find(p => p.name === name) || null,
    refresh:   ()   => {},
  });
  _pd.forEach((p, i) => { _pl[i] = p; });
  try { Object.defineProperty(navigator, 'plugins', { get: () => _pl }); } catch(_) {}

  // ─── MimeTypes ───────────────────────────────────────────────────────────
  const _md = [
    { type:'application/pdf', suffixes:'pdf', description:'Portable Document Format' },
    { type:'application/x-google-chrome-pdf', suffixes:'pdf', description:'Portable Document Format' },
    { type:'application/x-nacl',  suffixes:'', description:'Native Client Executable' },
    { type:'application/x-pnacl', suffixes:'', description:'Portable Native Client Executable' },
  ];
  const _mt = Object.assign([], {
    item:      i => _md[i] || null,
    namedItem: n => _md.find(m => m.type === n) || null,
  });
  _md.forEach((m, i) => { _mt[i] = m; });
  try { Object.defineProperty(navigator, 'mimeTypes', { get: () => _mt }); } catch(_) {}

  // ─── window.chrome (full real object) ────────────────────────────────────
  window.chrome = {
    app: {
      isInstalled: false,
      getDetails: () => null,
      getIsInstalled: () => false,
      InstallState: { DISABLED:'disabled', INSTALLED:'installed', NOT_INSTALLED:'not_installed' },
      RunningState: { CANNOT_RUN:'cannot_run', READY_TO_RUN:'ready_to_run', RUNNING:'running' },
    },
    runtime: {
      id: undefined,
      OnInstalledReason: { CHROME_UPDATE:'chrome_update', INSTALL:'install',
        SHARED_MODULE_UPDATE:'shared_module_update', UPDATE:'update' },
      PlatformArch: { ARM:'arm', ARM64:'arm64', X86_32:'x86-32', X86_64:'x86-64' },
      PlatformOs:   { ANDROID:'android', CROS:'cros', LINUX:'linux', MAC:'mac', WIN:'win' },
      RequestUpdateCheckStatus: { NO_UPDATE:'no_update', THROTTLED:'throttled', UPDATE_AVAILABLE:'update_available' },
    },
    loadTimes: function() {
      return {
        commitLoadTime: Date.now()/1000 - 0.4 - Math.random()*0.3,
        connectionInfo: 'h2', finishDocumentLoadTime: 0, finishLoadTime: 0,
        firstPaintAfterLoadTime: 0, firstPaintTime: 0,
        navigationType: 'Other', npnNegotiatedProtocol: 'h2',
        requestTime: Date.now()/1000 - 0.9, startLoadTime: Date.now()/1000 - 0.7,
        wasAlternateProtocolAvailable: false, wasFetchedViaSpdy: true, wasNpnNegotiated: true,
      };
    },
    csi: function() {
      return { onloadT: Date.now(), pageT: 4800 + Math.random()*2000,
               startE: Date.now() - 5000, tran: 15 };
    },
  };

  // ─── Permissions ─────────────────────────────────────────────────────────
  const _origPQ = window.navigator.permissions.query.bind(window.navigator.permissions);
  window.navigator.permissions.query = (params) =>
    params.name === 'notifications'
      ? Promise.resolve({ state: (typeof Notification !== 'undefined' ? Notification.permission : 'default') })
      : _origPQ(params);
  try { Object.defineProperty(Notification, 'permission', { get: () => 'default' }); } catch(_) {}

  // ─── WebGL — randomized GPU fingerprint ────────────────────────────────
  const _gpuPool = [
    ['Intel Inc.', 'Intel(R) Iris(TM) Plus Graphics 640'],
    ['Intel Inc.', 'Intel(R) UHD Graphics 620'],
    ['Intel Inc.', 'Intel(R) UHD Graphics 630'],
    ['Intel Inc.', 'Intel(R) HD Graphics 620'],
    ['Intel Inc.', 'Intel(R) HD Graphics 5500'],
    ['Intel Inc.', 'Intel(R) HD Graphics 4600'],
    ['Intel Inc.', 'Intel(R) HD Graphics 4000'],
    ['NVIDIA Corporation', 'GeForce GTX 1060 3GB/PCIe/SSE2'],
    ['NVIDIA Corporation', 'GeForce GTX 1050 Ti/PCIe/SSE2'],
    ['NVIDIA Corporation', 'GeForce RTX 2060/PCIe/SSE2'],
    ['NVIDIA Corporation', 'GeForce MX150/PCIe/SSE2'],
    ['AMD', 'AMD Radeon Pro 555X'],
    ['AMD', 'AMD Radeon RX 580 Series'],
    ['Apple Inc.', 'Apple M1'],
    ['Apple Inc.', 'Apple M2'],
    ['Apple Inc.', 'Apple GPU'],
  ];
  const [_gpuVendor, _gpuRenderer] = _gpuPool[Math.floor(Math.random() * _gpuPool.length)];

  const _gl1 = WebGLRenderingContext.prototype;
  const _ogp1 = _gl1.getParameter.bind(_gl1);
  _gl1.getParameter = function(p) {
    if (p === 37445) return _gpuVendor;
    if (p === 37446) return _gpuRenderer;
    return _ogp1.call(this, p);
  };
  if (typeof WebGL2RenderingContext !== 'undefined') {
    const _gl2 = WebGL2RenderingContext.prototype;
    const _ogp2 = _gl2.getParameter.bind(_gl2);
    _gl2.getParameter = function(p) {
      if (p === 37445) return _gpuVendor;
      if (p === 37446) return _gpuRenderer;
      return _ogp2.call(this, p);
    };
  }

  // ─── Canvas noise (subtle per-session, defeats fingerprinting) ───────────
  const _ns = (Math.random() * 0xFF | 0);
  const _orig_tdu = HTMLCanvasElement.prototype.toDataURL;
  HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
    if (this.width > 16 && this.height > 16) {
      try {
        const ctx = this.getContext('2d');
        if (ctx) { const d = ctx.getImageData(0,0,1,1); d.data[0]^=_ns; ctx.putImageData(d,0,0); }
      } catch(_) {}
    }
    return _orig_tdu.call(this, type, quality);
  };

  // ─── Consistent Date/timing jitter (prevents timing-based detection) ─────
  const _origNow = performance.now.bind(performance);
  performance.now = () => _origNow() + Math.random() * 0.1;

  // ─── Consistent iframe contentWindow check ────────────────────────────────
  // Some detectors check if an injected iframe's window looks automated
  const _origCreateEl = document.createElement.bind(document);
  document.createElement = function(tag, ...args) {
    const el = _origCreateEl(tag, ...args);
    if (tag.toLowerCase() === 'iframe') {
      Object.defineProperty(el, 'contentWindow', {
        get: function() {
          const cw = HTMLIFrameElement.prototype.__lookupGetter__('contentWindow').call(this);
          return cw;
        }
      });
    }
    return el;
  };

  // ─── AudioContext fingerprint spoofing ─────────────────────────────────────
  // Return consistent AudioContext fingerprint across sessions
  // Real AudioContext reveals hardware/sample rate info
  if (typeof AudioContext !== 'undefined') {
    const _origAC = AudioContext.bind(AudioContext);
    AudioContext = function() {
      const ac = new _origAC();
      // Stub out the Analyser so fingerprinting the frequency data is fruitless
      const _origCreateAnalyser = ac.createAnalyser.bind(ac);
      ac.createAnalyser = function() {
        const a = _origCreateAnalyser();
        a.getByteFrequencyData = a.getFloatFrequencyData = function() { return new Uint8Array(0); };
        return a;
      };
      return ac;
    };
    window.AudioContext = AudioContext;
    window.webkitAudioContext = AudioContext;
  }

  // ─── enumerateDevices — empty array, no hardware enumeration ──────────────
  if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
    const _origEnumerate = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
    navigator.mediaDevices.enumerateDevices = function() {
      return Promise.resolve([
        { kind: 'audiooutput', deviceId: 'default', label: 'default', groupId: 'default' },
        { kind: 'audioinput', deviceId: 'default', label: 'default', groupId: 'default' },
        { kind: 'videoinput', deviceId: 'default', label: 'default', groupId: 'default' },
      ]);
    };
  }

  // ─── CanvasRenderingContext2D.getImageData noise ────────────────────────────
  // Defeats canvas fingerprinting that reads pixel data directly
  const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
  let _canvasNoiseCounter = 0;
  const _canvasNoise = () => (_canvasNoiseCounter++ % 2 === 0) ? 1 : -1;
  CanvasRenderingContext2D.prototype.getImageData = function(sx, sy, sw, sh) {
    try {
      const id = _origGetImageData.call(this, sx, sy, sw, sh);
      // Add ±1 noise to a few random pixels so fingerprinting yields no stable result
      const d = id.data;
      const numPixelsToNudge = Math.min(8, Math.floor(d.length / 4));
      for (let i = 0; i < numPixelsToNudge; i++) {
        const idx = Math.floor(Math.random() * (d.length / 4)) * 4;
        d[idx] = Math.max(0, Math.min(255, d[idx] + _canvasNoise()));
      }
      return id;
    } catch(e) {
      return _origGetImageData.call(this, sx, sy, sw, sh);
    }
  };

  // ─── Navigator permissions — lie about camera/mic/background-sync ──────────
  if (navigator.permissions && navigator.permissions.query) {
    const _origPermissionsQuery = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = function(params) {
      const lying = ['camera', 'microphone', 'geolocation', 'notifications', 'background-sync',
                     'persistent-storage', 'midi', 'accelerometer', 'gyroscope', 'magnetometer'];
      if (lying.includes(params.name)) {
        return Promise.resolve({ state: 'granted', name: params.name,
          onchange: null, addEventListener: () => {}, removeEventListener: () => {} });
      }
      return _origPermissionsQuery(params);
    };
  }

  // ─── Battery API — already present but ensure no exceptions ───────────────
  if (navigator.getBattery && !navigator.getBattery._patched) {
    navigator.getBattery._patched = true;
    const _origGetBattery = navigator.getBattery.bind(navigator);
    navigator.getBattery = function() {
      return Promise.resolve({
        charging: true, chargingTime: 0, dischargingTime: Infinity,
        level: 0.75 + Math.random() * 0.25,
        addEventListener: () => {}, removeEventListener: () => {}
      });
    };
  }

  // ─── MediaCapabilities — lie about video codec support ─────────────────────
  if (navigator.mediaCapabilities) {
    const _origMC = navigator.mediaCapabilities.decodeAudioData
      ? navigator.mediaCapabilities : Object.create(navigator.mediaCapabilities);
    navigator.mediaCapabilities = {
      decodingInfo: async (config) => ({
        supported: true, powerful: true, smooth: true,
        configuration: config,
        keySystemAccess: null,
      }),
      encodingInfo: async (config) => ({
        supported: true, powerEfficient: true, smooth: true,
        configuration: config,
      }),
    };
  }

  // ─── Screen orientation — spoof to match viewport ──────────────────────────
  if (screen.orientation) {
    try {
      Object.defineProperty(screen.orientation, 'angle', { get: () => 0 });
      Object.defineProperty(screen.orientation, 'type', { get: () => 'landscape-primary' });
    } catch(_) {}
  }

  // ─── SpeechSynthesis — stable voices ────────────────────────────────────────
  if (window.speechSynthesis) {
    speechSynthesis.getVoices = () => [
      { name: 'Google US English', lang: 'en-US', localService: true, default: true },
      { name: 'Microsoft David', lang: 'en-US', localService: true, default: false },
      { name: 'Samantha', lang: 'en-US', localService: true, default: false },
    ];
  }

  // ─── DevicePixelRatio — randomize within plausible range ───────────────────
  const _origDPR = window.devicePixelRatio;
  const _newDPR = 1 + Math.random();   // 1.0 – 2.0 is most common real range
  Object.defineProperty(window, 'devicePixelRatio', { get: () => _newDPR });

  // ─── Touch support — indicate touch-capable hardware ────────────────────────
  Object.defineProperty(navigator, 'maxTouchPoints', { get: () => Math.floor(Math.random() * 10) });

  // ─── If platform is Mac — add Apple-specific lipids ────────────────────────
  const _ua = navigator.userAgent.toLowerCase();
  if (_ua.includes('mac') || _ua.includes('macos')) {
    try {
      const _macOSVersion = () => '10.15.7';
      // macOS undo manager — sites check for this to detect non-Safari
      document.__macOSVersion = _macOSVersion;
    } catch(_) {}
  }

  // ─── Final cleanup: remove any remaining Selenium/ CDP traces ───────────────
  ['__webdriver', '__selenium', '__driver_evaluate',
   '__webdriver_evaluate', '__selenium_evaluate',
   '__fxdriver_evaluate', 'selenium', 'webdriver'].forEach(p => {
    try { delete window[p]; } catch(_) {}
    try { Object.defineProperty(window, p, { get: () => undefined, configurable: true }); } catch(_) {}
  });
})();
"""

SYSTEM_PROMPT = open(os.path.join(os.path.dirname(__file__), "prompts", "system.md")).read()


class BrowserAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        *,
        proxy_provider: str = "generic",
        proxy_api_key: Optional[str] = None,
        proxy_zone: str = "residential",
        proxy_country: str = "us",
        proxy_url: Optional[str] = None,
        proxy_rotate_every: int = 20,
        session_name: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        self.model_name = model_name or os.getenv("AI_MODEL", "MiniMax-M2.7")
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.history: list = []
        self.conversation_history: list = []
        self._camoufox_ctx = None   # holds camoufox context manager for cleanup
        self._browser_engine = "chromium"

        # T036: nodriver bridge (holds the bridge when using nodriver engine)
        self._nodriver_bridge: Optional["NodriverBridge"] = None
        self._nodriver_driver: Optional[Any] = None  # raw ucd driver for ucd tier

        # Session persistence (Phase 2)
        self.session_name = session_name
        from session_manager import SessionManager
        self.session_manager = SessionManager(self)
        self.viewport = None   # set after _init_browser
        self.user_agent = None
        self.proxy_url = proxy_url

        # Proxy rotation
        self.proxy_manager = ProxyManager(
            provider=proxy_provider,
            api_key=proxy_api_key,
            zone=proxy_zone,
            country=proxy_country,
            proxy_url=proxy_url,
            rotate_every=proxy_rotate_every,
        )

        # Action history + undo (Phase 6)
        self.action_history = ActionHistory(self)

        # T009: workflow recorder (Phase 7)
        from workflow_recorder import WorkflowRecorder
        self.recorder = WorkflowRecorder(self, self.action_history)

        # T023: TLS fingerprint injection per session
        self._tls_inject: Optional[TLSInject] = None
        self._tls_profile_name: str = "chrome_win"

        # T030: Route interception for challenge detection
        self._route_interceptor: Optional[RouteInterceptor] = None
        self._challenge_escalation: bool = False
        self._challenge_domain: str = ""
        self._challenge_type: Optional[ChallengeType] = None

        # SQLite run history DB (Phase 4)
        self.run_db_id: Optional[int] = None

    def _build_ai_messages(self, task: str, page_content: str, screenshot_b64: str = None) -> list:
        """Build messages for AI including conversation history and optional screenshot for vision."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history)

        try:
            data = json.loads(page_content) if page_content.startswith("{") else {}
        except:
            data = {}

        form_lines = []
        form_map = data.get("form", {})
        if form_map:
            form_lines.append("FORM FIELDS:")
            for label, info in form_map.items():
                form_lines.append(f"  {label}: {info['selector']} (type={info['type']})")

        # Phase 3.2: include select options
        select_options = data.get("select_options", {})
        if select_options:
            form_lines.append("SELECT DROPDOWNS:")
            for name, info in select_options.items():
                opts = ", ".join(f"'{o['value']}'" + (" [SELECTED]" if o.get("selected") else "") for o in info["options"])
                form_lines.append(f"  {name} ({info['selector']}): {opts}")

        interactives = data.get("interactives", [])
        int_lines = []
        if interactives:
            int_lines.append("INTERACTIVE:")
            for el in interactives:
                if el["tag"] in ("button", "a") or el["type"] in ("submit", "button"):
                    int_lines.append(f"  {el['text'] or el['selector']}: {el['selector']}")
                elif el["tag"] == "input":
                    int_lines.append(f"  [{el['type']}] {el['selector']}: placeholder='{el['placeholder'] or ''}' current='{el.get('value','')}'")

        # Phase 3.2: page state warnings
        warnings = []
        page_state = data.get("page_state", "")
        if page_state == "spa/dynamic":
            warnings.append("⚠ PAGE IS DYNAMIC/SPA — content may load after initial render")
        captcha = data.get("captcha")
        if captcha:
            warnings.append(f"⚠ CAPTCHA DETECTED: {captcha}")
        iframe_count = data.get("iframe_count", 0)
        if iframe_count > 0:
            warnings.append(f"ℹ {iframe_count} iframe(s) on page")
        shadow_dom_count = data.get("shadow_dom_count", 0)
        if shadow_dom_count > 0:
            warnings.append(f"ℹ {shadow_dom_count} shadow DOM element(s)")
        login_wall = data.get("login_wall")
        if login_wall and login_wall.get("detected"):
            if login_wall.get("has_skip"):
                warnings.append(f"⚠ LOGIN WALL DETECTED — page redirected to login/signup. Try: {login_wall.get('skip_selector', 'skip/guest link')} to bypass.")
            else:
                warnings.append("⚠ LOGIN WALL DETECTED — page requires login/signup. No skip/guest option found. Report to user.")

        content_parts = [f"Task: {task}"]

        # ── Domain memory: inject learned context if we've visited this domain before ─
        try:
            from domain_memory import inject_domain_context
            if self.page and not self.page.is_closed():
                current_url = self.page.url
                if current_url:
                    from urllib.parse import urlparse
                    domain = urlparse(current_url).netloc
                    if domain:
                        # Replace the bare task line with domain-memory-enhanced version
                        content_parts[0] = inject_domain_context(f"Task: {task}", domain)
        except Exception:
            pass  # Domain memory is best-effort

        if warnings:
            content_parts.append("PAGE WARNINGS: " + " | ".join(warnings))
        if form_lines:
            content_parts.append("\n".join(form_lines))
        if int_lines:
            content_parts.append("\n".join(int_lines))
        content_parts.append(f"\nPage: {data.get('title','unknown')} — {data.get('url','')}")

        content = "\n".join(content_parts)
        messages.append({"role": "user", "content": content[:3000]})
        return messages

    async def _init_browser(self):
        """5-tier stealth browser init.

        Tier 1: camoufox + Xvfb virtual display (real Firefox, zero headless flags)
        Tier 2: camoufox headless (Firefox, real TLS/HTTP2 fingerprint)
        Tier 3: Chromium + STEALTH_JS (comprehensive JS patches)
        Tier 4: undetected-chromedriver (full CDP/ChromeDriver stealth)
        Tier 5: Crawlee JSDOM (no browser — pure JS rendering for heavy antibot sites)

        Set BROWSER_ENGINE=camoufox-virtual|camoufox|chromium|ucd|crawlee
        to force a specific engine. Default: auto-fallback in order above.
        Proxy is applied to all tiers via proxy_manager.
        """
        if self.browser is not None:
            return

        profile = random.choice(_PROFILES)
        screen  = random.choice(_SCREEN_SIZES)

        # ── Viewport & screen randomization ─────────────────────────────────
        vp_w = screen["width"]  + random.randint(-20, 20)
        vp_h = screen["height"] + random.randint(-20, 20)
        vp_w = max(1024, min(3840, vp_w))
        vp_h = max(576,  min(2160, vp_h))
        scr_w = vp_w + random.randint(0, 64)
        scr_h = vp_h + random.randint(40, 120)

        # Get proxy for this session (all tiers)
        proxy_url = None
        if self.proxy_manager:
            try:
                proxy_url = await asyncio.get_event_loop().run_in_executor(
                    None, self.proxy_manager.get_proxy
                )
                logger.info(f"Using proxy: {proxy_url}")
            except Exception as e:
                logger.warning(f"Proxy fetch failed: {e} — continuing without proxy")

        forced_engine = os.getenv("BROWSER_ENGINE", "")

        # ── Tier 1: camoufox + Xvfb virtual display ──────────────────────────
        if not forced_engine or forced_engine == "camoufox-virtual":
            try:
                from camoufox.async_api import AsyncCamoufox
                extra_opts = {"block_webrtc": True}
                if proxy_url:
                    extra_opts["proxy"] = proxy_url
                self._camoufox_ctx = AsyncCamoufox(
                    headless="virtual",
                    os=profile["os"],
                    **extra_opts,
                )
                self.browser = await self._camoufox_ctx.__aenter__()
                self._browser_engine = "camoufox-virtual"
                logger.info("Engine: camoufox/Firefox + Xvfb virtual display (tier 1)")
            except Exception as e1:
                logger.warning(f"Tier 1 (camoufox virtual) failed: {e1!r}")
                self._camoufox_ctx = None

                # ── Tier 2: camoufox headless ─────────────────────────────────
                if not forced_engine or forced_engine == "camoufox":
                    try:
                        extra_opts = {"block_webrtc": True}
                        if proxy_url:
                            extra_opts["proxy"] = proxy_url
                        self._camoufox_ctx = AsyncCamoufox(
                            headless=True,
                            os=profile["os"],
                            **extra_opts,
                        )
                        self.browser = await self._camoufox_ctx.__aenter__()
                        self._browser_engine = "camoufox"
                        logger.info("Engine: camoufox/Firefox headless (tier 2)")
                    except Exception as e2:
                        logger.warning(f"Tier 2 (camoufox headless) failed: {e2!r}")
                        self._camoufox_ctx = None

                        # ── Tier 3: Chromium + STEALTH_JS ─────────────────────
                        if not forced_engine or forced_engine == "chromium":
                            try:
                                if self.playwright is None:
                                    self.playwright = await async_playwright().start()
                                chromium_opts = {
                                    "args": STEALTH_ARGS,
                                    "headless": True,
                                    "ignore_default_args": ["--enable-automation"],
                                }
                                if proxy_url:
                                    chromium_opts["proxy"] = {"server": proxy_url}
                                self.browser = await self.playwright.chromium.launch(**chromium_opts)
                                self._browser_engine = "chromium"
                                logger.info("Engine: Chromium + STEALTH_JS (tier 3)")
                            except Exception as e3:
                                logger.warning(f"Tier 3 (chromium) failed: {e3!r}")

                                # ── Tier 3.5: nodriver stealth + Playwright CDP ─────────────
                                # nodriver patches Chrome at runtime to remove automation signals.
                                # Playwright connects to it via CDP websocket URL, giving us:
                                #   nodriver stealth + Playwright API + our TLS/JS spoofing layers.
                                if not forced_engine or forced_engine == "nodriver":
                                    try:
                                        bridge = NodriverBridge(
                                            headless=True,
                                            proxy=proxy_url,
                                        )
                                        pw, pw_browser, page = await bridge.start()
                                        # Store on self for cleanup in cleanup_browser()
                                        self._nodriver_bridge = bridge
                                        self.playwright = pw
                                        self.browser = pw_browser   # Playwright browser (connected via CDP)
                                        self.page = page
                                        self._browser_engine = "nodriver"
                                        logger.info("Engine: nodriver stealth + Playwright CDP (tier 3.5)")
                                        # Jump straight to TLS/profile setup — skip the context/page setup below
                                        self._tls_profile_name = "chrome_win" if profile["os"] == "windows" else "chrome_mac"
                                        self._tls_inject = TLSInject(profile_name=self._tls_profile_name)
                                        # Apply TLS inject + enhanced stealth on nodriver's page
                                        await self.context.add_init_script(
                                            HEADLESS_DETECTION_BYPASS
                                        )
                                        tls_headers = self._tls_inject.get_client_hints()
                                        if tls_headers:
                                            await self.page.set_extra_http_headers(tls_headers)
                                        try:
                                            await self._tls_inject.apply_via_cdp(self.page)
                                        except Exception as tls_err:
                                            logger.warning(f"[TLS] CDP injection skipped: {tls_err}")
                                        # Register route interceptor for challenge detection
                                        ri = RouteInterceptor(log=logger)
                                        await ri.register(self.page)
                                        return  # ← skip the context/page setup below
                                    except Exception as e35:
                                        logger.warning(f"Tier 3.5 (nodriver) failed: {e35!r}")

                                # ── Tier 4: undetected-chromedriver ─────────────
                                if not forced_engine or forced_engine == "ucd":
                                    try:
                                        import undetected_chromedriver as ucd
                                        ucd_opts = {
                                            "headless": True,
                                            "use_auto_implicit_wait": True,
                                            "no_sandbox": True,
                                        }
                                        if proxy_url:
                                            proxy_parts = proxy_url.replace("http://", "").split("@")
                                            if len(proxy_parts) == 2:
                                                ucd_opts["proxy"] = proxy_parts[1]
                                            else:
                                                ucd_opts["proxy"] = proxy_url
                                        ucd_driver = await asyncio.get_event_loop().run_in_executor(
                                            None,
                                            lambda: ucd.Chrome(**ucd_opts)
                                        )
                                        # Wrap ucd browser in a Playwright-compatible interface
                                        # ucd exposes .page via driver.window
                                        self._ucd_driver = ucd_driver
                                        self._browser_engine = "ucd"
                                        logger.info("Engine: undetected-chromedriver (tier 4)")
                                    except Exception as e4:
                                        logger.warning(f"Tier 4 (ucd) failed: {e4!r}")

                                        # ── Tier 5: Crawlee JSDOM ───────────────────
                                        if not forced_engine or forced_engine == "crawlee":
                                            try:
                                                from crawlee.crawlers import PlaywrightCrawler
                                                crawlee_crawler = PlaywrightCrawler(
                                                    headless=True,
                                                    browser_launch_options={"chromium_sandbox": False},
                                                )
                                                # Crawlee manages its own browser pool
                                                self._crawlee_crawler = crawlee_crawler
                                                self._browser_engine = "crawlee-jsdom"
                                                logger.info("Engine: Crawlee JSDOM (tier 5)")
                                            except ImportError:
                                                logger.warning("Crawlee not installed — install with: pip install crawlee")
                                                raise
                                            except Exception as e5:
                                                logger.warning(f"Tier 5 (crawlee) failed: {e5!r}")
                                                raise RuntimeError(
                                                    "All browser tiers failed. "
                                                    "Install undetected-chromedriver: pip install undetected-chromedriver\n"
                                                    "Install crawlee: pip install crawlee"
                                                )

        # ── T023: TLS fingerprint profile selection ──────────────────────────────────
        # Match TLS profile to browser engine for consistency across TLS + HTTP layers
        if "firefox" in self._browser_engine or "camoufox" in self._browser_engine:
            self._tls_profile_name = "firefox_win"
        elif "safari" in self._browser_engine:
            self._tls_profile_name = "safari_mac"
        else:
            # Chromium-based engines — pick OS variant
            self._tls_profile_name = "chrome_win" if profile["os"] == "windows" else "chrome_mac"

        self._tls_inject = TLSInject(profile_name=self._tls_profile_name)
        logger.info(f"[TLS] Profile: {self._tls_profile_name}")

        # ── Context + page setup (all Playwright-compatible tiers) ─────────────
        if self._browser_engine in ("camoufox-virtual", "camoufox"):
            self.page    = await self.browser.new_page()
            self.context = self.page.context

            # Build headers: base + TLS inject (Sec-CH-UA client hints + JA3/JA4)
            base_headers = {
                "Accept-Language": f"{profile['locale']},{profile['locale'][:2]};q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }
            # T028: Merge in Sec-CH-UA and other client hint headers
            tls_headers = self._tls_inject.get_client_hints()
            merged_headers = {**base_headers, **tls_headers}

            await self.context.add_init_script(
                STEALTH_JS +
                "\ntry{"
                "\n  if (window.outerWidth <= window.innerWidth) {"
                "\n    Object.defineProperty(window,'outerWidth',  {get:()=>window.innerWidth+16});"
                "\n    Object.defineProperty(window,'outerHeight', {get:()=>window.innerHeight+92});"
                "\n  }"
                "\n  ['__playwright','__pw_manual','_playwrightCommandCounts'].forEach(p=>{"
                "\n    try{delete window[p];}catch(_){}"
                "\n  });"
                "\n}catch(_){}"
                "\n" + f"Object.defineProperty(window,'outerWidth',  {{get:()=>{vp_w}}});"
                "\n" + f"Object.defineProperty(window,'outerHeight', {{get:()=>{vp_h}}});"
            )
            await self.page.set_extra_http_headers(merged_headers)
        elif self._browser_engine in ("chromium", "ucd"):
            # Build headers: base + TLS inject + Sec-CH-UA (T023, T028)
            base_headers = {
                "Accept-Language": f"{profile['locale']},{profile['locale'][:2]};q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }
            # T023: Merge TLS inject headers (JA3/JA4 correlation + Sec-CH-UA client hints)
            tls_headers = self._tls_inject.get_client_hints()
            merged_headers = {**base_headers, **tls_headers}

            context_opts = {
                "viewport": {"width": vp_w, "height": vp_h},
                "screen": {"width": scr_w, "height": scr_h},
                "locale": profile["locale"],
                "timezone_id": profile["timezone_id"],
                "user_agent": random.choice(USER_AGENTS),
                "color_scheme": random.choice(["dark", "light", "light"]),
                "extra_http_headers": merged_headers,
            }
            if proxy_url:
                context_opts["proxy"] = {"server": proxy_url}
            self.context = await self.browser.new_context(**context_opts)
            self.page = await self.context.new_page()

            # T024: Enhanced stealth JS: inject headless bypass + WebGL + plugins spoofing
            # This is appended AFTER STEALTH_JS so it overrides/extends base patches
            await self.context.add_init_script(
                STEALTH_JS +
                HEADLESS_DETECTION_BYPASS +
                f"\nObject.defineProperty(window,'outerWidth',  {{get:()=>{vp_w}}})"
                f"\nObject.defineProperty(window,'outerHeight', {{get:()=>{vp_h}}})"
            )

            # T023: Try CDP-based TLS channel ID injection (Chromium only)
            try:
                await self._tls_inject.apply_via_cdp(self.page)
            except Exception as tls_cdp_err:
                logger.warning(f"[TLS] CDP injection skipped: {tls_cdp_err}")
        elif self._browser_engine == "crawlee-jsdom":
            # Crawlee manages its own page — just open a fresh page
            self.context = None
            self.page = await self._crawlee_crawler.browser_pool.get_free_page()
            if self.page is None:
                raise RuntimeError("Crawlee failed to provide a page")

        self.page.set_default_timeout(15000)
        self.page.set_default_navigation_timeout(30000)

        # T030: Register route interception for challenge detection
        if self._route_interceptor is None:
            self._route_interceptor = RouteInterceptor(self)
            await self._route_interceptor.register(self.page)
            logger.info("[RouteInt] Registered on first page")

        # Auto-load named session after browser launch (Phase 2)
        if self.session_name:
            try:
                await self.session_manager.load_session(self.session_name)
                logger.info(f"Session '{self.session_name}' loaded on startup")
            except Exception as e:
                logger.warning(f"Failed to load session '{self.session_name}': {e}")

    async def _dismiss_captcha_iframe(self):
        """BUG-02 fix: Detect and auto-dismiss CAPTCHA/delivery iframes.
        Detects: captcha-delivery.com, hcaptcha, recaptcha, cloudflare challenges.
        Returns the domain of any CAPTCHA detected (or None)."""
        CAPTCHA_DOMAINS = [
            "captcha-delivery.com",
            "hcaptcha.com",
            "recaptcha.net",
            "google.com/recaptcha",
            "cloudflare.com/cfdn",
            "challenges.cloudflare.com",
            "data-media.io",
            "privacy-mgmt.com",
        ]
        try:
            iframes = await self.page.query_selector_all("iframe")
            for iframe in iframes:
                try:
                    src = await iframe.get_attribute("src") or ""
                    for domain in CAPTCHA_DOMAINS:
                        if domain in src.lower():
                            box = await iframe.bounding_box()
                            if box and box["width"] > 10 and box["height"] > 10:
                                logger.info(f"CAPTCHA iframe detected: {domain} — auto-closing")
                                await iframe.evaluate("el => el.remove()")
                                await self._human_delay(0.3, 0.6)
                                return domain
                except Exception:
                    continue
            return None
        except Exception as e:
            logger.warning(f"CAPTCHA iframe check failed: {e}")
            return None

    async def _handle_captcha_iframe(self) -> bool:
        """T010: Attempt to solve CAPTCHA iframes via configured provider.
        Returns True if CAPTCHA was detected and solved, False otherwise.
        """
        captcha_type = None
        try:
            iframes = await self.page.query_selector_all("iframe")
            for iframe in iframes:
                try:
                    src = await iframe.get_attribute("src") or ""
                    src_lower = src.lower()
                    if "hcaptcha" in src_lower or "h-captcha" in src_lower:
                        captcha_type = TYPE_HCAPTCHA
                    elif "recaptcha" in src_lower or "google.com/recaptcha" in src_lower:
                        captcha_type = TYPE_RECAPTCHA_V2
                    elif "turnstile" in src_lower or "cloudflare" in src_lower:
                        captcha_type = TYPE_TURNSTILE
                    elif any(d in src_lower for d in ("captcha-delivery", "privacy-mgmt", "data-media")):
                        captcha_type = TYPE_HCAPTCHA  # treat as hcaptcha default

                    if captcha_type:
                        box = await iframe.bounding_box()
                        if box and box["width"] > 10 and box["height"] > 10:
                            site_key = detect_site_key(self.page, captcha_type)
                            if site_key:
                                api_key = os.environ.get("CAPTCHA_API_KEY") or os.environ.get("_2CAPTCHA_API_KEY", "")
                                provider = os.environ.get("CAPTCHA_PROVIDER", "2captcha")
                                if api_key:
                                    logger.info(f"[CAPTCHA] Solving {captcha_type} with {provider}, sitekey={site_key[:20]}...")
                                    token = await solve_captcha(
                                        api_key, captcha_type, site_key,
                                        self.page.url, provider
                                    )
                                    if token:
                                        logger.info(f"[CAPTCHA] Solved — injecting token")
                                        # Inject the token into the CAPTCHA callback
                                        await self.page.evaluate(
                                            f"""(token) => {{
                                                // Try hCaptcha
                                                if (window.hcaptcha) window.hcaptcha.submit(token);
                                                // Try reCAPTCHA
                                                if (window.___grecaptcha_cfg) {{
                                                    Object.keys(window.___grecaptcha_cfg.clients).forEach(k => {{
                                                        window.___grecaptcha_cfg.clients[k].ready?.(token);
                                                    }});
                                                }}
                                                // Try Turnstile
                                                if (window.turnstile) window.turnstile.submit(token);
                                                // Try generic callback
                                                if (window._captcha_callback) window._captcha_callback(token);
                                                // Generic textarea injection (some sites read from here)
                                                const textareas = document.querySelectorAll('textarea[name*="captcha"], textarea[id*="captcha"]');
                                                textareas.forEach(t => t.value = token);
                                            }}""", token
                                        )
                                        await self._human_delay(1.0, 1.5)
                                        return True
                                    else:
                                        logger.warning("[CAPTCHA] Solve returned no token — falling back to dismiss")
                                else:
                                    logger.info("[CAPTCHA] No API key — will dismiss iframe")
                            # Remove the iframe either way
                            await iframe.evaluate("el => el.remove()")
                            return False
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"[CAPTCHA] Handle error: {e}")
        return False

    async def _human_scroll(self, direction: str = "down", fraction: float = None):
        """Scroll with human-like randomisation (Phase 3.4).

        Args:
            direction: 'down' or 'up'
            fraction: optional 0.0–1.0 override — fraction of viewport height to scroll.
                      None = random 0.3–0.8 of viewport height.
        """
        if fraction is None:
            fraction = random.uniform(0.3, 0.8)

        if direction == "down":
            sign = -1
        elif direction == "up":
            sign = 1
        else:
            # random direction
            sign = random.choice([-1, 1])

        viewport = self.page.viewport_size or {"width": 1280, "height": 720}
        scroll_px = int(sign * fraction * viewport["height"])

        # Add slight horizontal drift (1–15% of vertical scroll)
        h_drift = int(scroll_px * random.uniform(0.01, 0.15))
        h_drift *= random.choice([-1, 1])

        # Small pause before scroll
        await asyncio.sleep(random.uniform(0.05, 0.2))
        await self.page.evaluate(
            f"(x, y) => window.scrollBy({{ top: {scroll_px}, left: {h_drift}, behavior: 'smooth' }})",
            0, 0
        )
        # Pause after scroll to let animation settle
        await asyncio.sleep(random.uniform(0.2, 0.5))

    async def _human_move(self, target_x: int, target_y: int):
        """Move mouse to target position via bezier curve (Phase 3.4).

        Replaces plain page.mouse.move() with a multi-step curved path
        that accelerates then decelerates — much harder to detect as bot.
        """
        start_x = random.randint(50, 700)
        start_y = random.randint(50, 500)

        # 4–8 waypoints for a natural-looking curve
        steps = random.randint(4, 8)
        duration_ms = random.randint(400, 1000)
        step_ms = duration_ms / steps

        # Bezier control points — make it arc naturally above/below the straight line
        cp1x = start_x + (target_x - start_x) * random.uniform(0.2, 0.4)
        cp1y = start_y + (target_y - start_y) * random.uniform(-0.4, -0.1)  # arc upward
        cp2x = start_x + (target_x - start_x) * random.uniform(0.6, 0.8)
        cp2y = start_y + (target_y - start_y) * random.uniform(1.1, 1.4)   # arc downward

        # Generate points along cubic bezier
        import math
        points = []
        for t in [i / steps for i in range(steps + 1)]:
            t2 = t * t
            t3 = t2 * t
            mt = 1 - t
            mt2 = mt * mt
            mt3 = mt2 * mt
            px = mt3 * start_x + 3 * mt2 * t * cp1x + 3 * mt * t2 * cp2x + t3 * target_x
            py = mt3 * start_y + 3 * mt2 * t * cp1y + 3 * mt * t2 * cp2y + t3 * target_y
            # Add micro-jitter
            px += random.gauss(0, 1.5)
            py += random.gauss(0, 1.5)
            points.append((round(px, 1), round(py, 1)))

        for i, (x, y) in enumerate(points):
            await self.page.mouse.move(x, y)
            # Slow down near the end (deceleration)
            delay = step_ms * (1.5 if i > steps * 0.7 else 1.0)
            await asyncio.sleep(delay / 1000)

    async def _human_delay(self, min_s: float = 0.5, max_s: float = 2.0):
        """Random delay mimicking human speed"""
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def _human_type(self, selector: str, text: str):
        """Type text character-by-character with variable delays, rare typos+corrections."""
        # Click / focus the field
        try:
            await self.page.click(selector, timeout=6000)
        except Exception:
            await self.page.focus(selector)
        await asyncio.sleep(random.uniform(0.08, 0.25))

        # Clear any existing value first
        await self.page.keyboard.press("Control+a")
        await asyncio.sleep(random.uniform(0.04, 0.10))
        await self.page.keyboard.press("Backspace")
        await asyncio.sleep(random.uniform(0.05, 0.12))

        # Base typing speed: 45–100 ms/char (realistic human range)
        base_ms = random.uniform(45, 100)

        i = 0
        while i < len(text):
            char = text[i]

            # 1.5% chance of a fat-finger typo on alphabetic keys
            if random.random() < 0.015 and char.isalpha() and i > 0:
                typo = random.choice("asdfjkl;qwerty")
                await self.page.keyboard.type(typo)
                await asyncio.sleep(random.uniform(0.06, 0.14))
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.04, 0.10))

            await self.page.keyboard.type(char)

            # Variable delay: pause longer after spaces/punctuation
            if char == " ":
                delay = random.uniform(0.07, 0.22)
            elif char in ".,!?;:":
                delay = random.uniform(0.10, 0.28)
            elif char in "\n\r":
                delay = random.uniform(0.15, 0.35)
            else:
                delay = (base_ms / 1000) * random.uniform(0.4, 1.9)

            await asyncio.sleep(delay)
            i += 1

        # Brief settle after finishing
        await asyncio.sleep(random.uniform(0.05, 0.15))

    async def _get_page_content(self) -> str:
        """Get rich structured page content for AI — includes SPA detection, selects, iframes, CAPTCHAs."""
        try:
            # First wait briefly for dynamic content to settle
            # Use domcontentloaded (fast) + small sleep instead of networkidle
            # (networkidle waits for ALL network activity — analytics/ads cause it to hang)
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            # Brief additional settle time for SPA hydration
            await asyncio.sleep(1.0)

            content = await self.page.evaluate("""() => {
                const body = document.body;
                if (!body) return JSON.stringify({error: 'Empty page'});

                // ── SPA / dynamic page detection ──────────────────────────────────
                const networkRequests = window.performance && window.performance.getEntries
                    ? window.performance.getEntriesByType('resource').length : -1;
                const hasMutationObserver = typeof MutationObserver !== 'undefined';
                const hasPendingRequests = document.readyState !== 'complete';

                // ── Cookie / consent banner detection ─────────────────────────────
                const cookieBannerSelectors = [
                    '[aria-label*="cookie" i]', '[class*="cookie" i]', '[id*="cookie" i]',
                    '[class*="consent" i]', '[id*="consent" i]', '[class*="gdpr" i]',
                    '[aria-label*="accept" i]', '[aria-label*="allow" i]',
                ];
                let cookieBannerDetected = null;
                let cookieBannerText = null;
                for (const sel of cookieBannerSelectors) {
                    const el = document.querySelector(sel);
                    if (el && window.getComputedStyle(el).display !== 'none') {
                        cookieBannerDetected = sel;
                        cookieBannerText = el.textContent ? el.textContent.trim().slice(0, 200) : sel;
                        break;
                    }
                }
                // ── YouTube GDPR consent page ─────────────────────────────────────
                if (window.location.hostname === 'consent.youtube.com' ||
                    document.title === 'Before you continue to YouTube' ||
                    document.querySelector('[action*="consent"]')) {
                    const heading = document.querySelector('h1, h2, [aria-label*="continue"]')?.textContent?.trim() || '';
                    const subtext = document.querySelector('p, [class*="body"]')?.textContent?.trim().slice(0, 200) || '';
                    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"]'))
                        .map(b => b.textContent?.trim() || b.value || '').filter(Boolean).slice(0, 5);
                    cookieBannerDetected = 'youtube_gdpr';
                    cookieBannerText = `GDPR_CONSENT: "${heading}" | "${subtext}" | Buttons: ${buttons.join(', ')}`;
                }

                // ── CAPTCHA / Cloudflare detection ───────────────────────────────
                let captchaDetected = null;
                const cfChallenge = document.querySelector('#cf-challenge-center, #challenge-form, .cf-challenge');
                const hcaptcha = document.querySelector('.h-captcha');
                const recaptcha = document.querySelector('.g-recaptcha');
                const genericCaptcha = document.querySelector('[class*="captcha" i], [id*="captcha" i]');
                if (cfChallenge) captchaDetected = 'cloudflare';
                else if (hcaptcha) captchaDetected = 'hcaptcha';
                else if (recaptcha) captchaDetected = 'recaptcha';
                else if (genericCaptcha) captchaDetected = 'generic';

                // ── Login wall / auth wall detection ────────────────────────────────
                let loginWall = null;
                const currentUrl = window.location.href.toLowerCase();
                const hasEmailField = !!document.querySelector('input[type="email"], input[name*="email"], input[name*="login"], input[placeholder*="email" i]');
                const hasPasswordField = !!document.querySelector('input[type="password"]');
                const loginKeywords = ['sign in', 'log in', 'login', 'create account', 'sign up', 'register'];
                const pageTextLower = (document.body?.textContent || '').toLowerCase().slice(0, 2000);
                const hasLoginKeyword = loginKeywords.some(kw => pageTextLower.includes(kw));
                const loginUrls = ['/login', '/signin', '/sign-in', '/auth', '/account/login'];
                const hasLoginUrl = loginUrls.some(u => currentUrl.includes(u));
                if ((hasEmailField && hasPasswordField) || (hasLoginUrl && hasLoginKeyword)) {
                    const skipLinks = Array.from(document.querySelectorAll('a, button')).filter(el => {
                        const t = (el.textContent || '').toLowerCase();
                        return ['skip', 'guest', 'browse without', 'continue without', 'later', 'no thanks', 'not now'].some(kw => t.includes(kw));
                    });
                    loginWall = {
                        detected: true,
                        url: window.location.href,
                        has_skip: skipLinks.length > 0,
                        skip_selector: skipLinks[0] ? (skipLinks[0].id ? '#' + skipLinks[0].id : (skipLinks[0].className ? 'a.' + skipLinks[0].className.split(' ')[0] : 'a')) : null
                    };
                }

                // ── Shadow DOM elements ──────────────────────────────────────────
                const shadowHosts = document.querySelectorAll('*');
                let shadowDomCount = 0;
                for (const el of shadowHosts) {
                    if (el.shadowRoot) shadowDomCount++;
                }

                // ── Modal / popup / overlay dialogs ──────────────────────────────
                // Detect any visible modal, dialog, overlay, or full-screen popup
                let popupDialog = null;
                const modalSelectors = [
                    '[role="dialog"]', '[role="alertdialog"]', '.modal', '.Modal',
                    '[class*="modal"]', '[class*="Modal"]', '[class*="overlay"]',
                    '[class*="Overlay"]', '[class*="popup"]', '[class*="Popup"]',
                    '[class*="consent"]', '[class*="Consent"]', '[id*="consent"]',
                    '[id*="Consent"]', '[aria-modal="true"]', '.遮罩', // Chinese "mask"
                    '.cookies', '.Cookies', '.gdpr', '.GDPR',
                ];
                for (const sel of modalSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const style = window.getComputedStyle(el);
                        const isVisible = style.display !== 'none' &&
                                          style.visibility !== 'hidden' &&
                                          el.offsetWidth > 0 &&
                                          el.offsetHeight > 0;
                        if (isVisible) {
                            const heading = el.querySelector('h1, h2, h3, [aria-label]')?.textContent?.trim().slice(0, 100) || '';
                            const body = el.textContent?.trim().slice(0, 300) || '';
                            popupDialog = { selector: sel, heading, body };
                            break;
                        }
                    }
                }
                // Also check for full-screen wrappers (YouTube consent style)
                if (!popupDialog) {
                    const body = document.body;
                    if (body && body.offsetWidth > 0 && body.offsetHeight > 0) {
                        const children = Array.from(body.children);
                        for (const child of children) {
                            const style = window.getComputedStyle(child);
                            if (child.tagName !== 'SCRIPT' && child.tagName !== 'STYLE' &&
                                style.position === 'fixed' && child.offsetWidth > body.offsetWidth * 0.5) {
                                popupDialog = {
                                    selector: child.className ? `.${child.className.split(' ')[0]}` : child.tagName,
                                    heading: child.querySelector('h1,h2')?.textContent?.trim().slice(0, 100) || '',
                                    body: child.textContent?.trim().slice(0, 300) || ''
                                };
                                break;
                            }
                        }
                    }
                }

                // ── Iframe count ───────────────────────────────────────────────
                const iframes = document.querySelectorAll('iframe');
                const iframeInfo = Array.from(iframes).map(f => ({
                    src: f.src ? f.src.slice(0, 80) : '',
                    visible: f.offsetWidth > 0 && f.offsetHeight > 0,
                }));

                // ── ARIA live regions ───────────────────────────────────────────
                const ariaLive = Array.from(document.querySelectorAll('[aria-live]'))
                    .map(el => ({ tag: el.tagName.toLowerCase(), text: el.textContent.trim().slice(0, 60), politeness: el.getAttribute('aria-live') }));

                // ── Select options ─────────────────────────────────────────────
                const selectMap = {};
                document.querySelectorAll('select').forEach(sel => {
                    const name = sel.getAttribute('name') || sel.id || sel.className || sel.tagName.toLowerCase();
                    const options = Array.from(sel.options).map(opt => ({
                        text: opt.text.trim().slice(0, 60),
                        value: opt.value,
                        selected: opt.selected,
                    }));
                    selectMap[name] = { selector: (sel.getAttribute('name') ? `select[name="${sel.getAttribute('name')}"]` : sel.id ? `#${sel.id}` : sel.tagName.toLowerCase()), options };
                });

                // ── Image alt text ─────────────────────────────────────────────
                const images = Array.from(document.images).slice(0, 20).map(img => ({
                    alt: img.alt || '',
                    src: img.src ? img.src.slice(0, 80) : '',
                    width: img.naturalWidth,
                }));

                const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
                    acceptNode: (node) => {
                        const style = window.getComputedStyle(node.parentElement);
                        return style.display !== 'none' && style.visibility !== 'hidden'
                            ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                    }
                });

                const texts = [];
                while (walker.nextNode()) {
                    const t = walker.currentNode.textContent.trim();
                    if (t) texts.push(t);
                }

                const formMap = {};
                document.querySelectorAll('input, select, textarea').forEach(el => {
                    const name = el.getAttribute('name') || el.id || '';
                    const type = el.getAttribute('type') || '';
                    const value = el.getAttribute('value') || '';
                    let label = '';
                    const forAttr = el.getAttribute('id');
                    if (forAttr) {
                        const lbl = document.querySelector('label[for="' + forAttr + '"]');
                        if (lbl) label = lbl.textContent.trim();
                    }
                    if (!label && name) {
                        const lbl = document.querySelector('label[for="' + name + '"]');
                        if (lbl) label = lbl.textContent.trim();
                    }
                    const hint = type === 'radio' || type === 'checkbox' ? `[value="${value}"]` : '';
                    const selector = name ? `${el.tagName.toLowerCase()}[name="${name}"]` : (el.id ? '#' + el.id : el.tagName.toLowerCase());
                    const key = label || (type === 'radio' || type === 'checkbox' ? value : name || selector);
                    formMap[key] = {selector: selector + hint, type, value};
                });

                const interactives = [];
                document.querySelectorAll('a, button, input, select, textarea, [role="button"], [onclick]').forEach(el => {
                    const tag = el.tagName.toLowerCase();
                    const text = el.textContent?.trim()?.slice(0, 50) || '';
                    const href = el.getAttribute('href') || '';
                    const type = el.getAttribute('type') || '';
                    const name = el.getAttribute('name') || '';
                    const id = el.getAttribute('id') || '';
                    const cls = el.getAttribute('class') || '';
                    const placeholder = el.getAttribute('placeholder') || '';

                    let selector = '';
                    if (id) selector = '#' + id;
                    else if (name) selector = `${tag}[name="${name}"]`;
                    else if (cls) selector = `${tag}.${cls.split(' ')[0]}`;
                    else selector = tag;

                    interactives.push({
                        selector,
                        tag,
                        text: text.slice(0, 30),
                        href: href.slice(0, 50),
                        type,
                        placeholder: placeholder.slice(0, 30),
                        value: (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') ? (el.value || '') : '',
                    });
                });

                return JSON.stringify({
                    url: window.location.href,
                    title: document.title,
                    text: texts.slice(0, 200).join(' ').slice(0, 4000),
                    form: formMap,
                    interactives: interactives.slice(0, 60),
                    // Phase 3.2 enriched fields
                    page_state: hasPendingRequests ? 'spa/dynamic' : 'static',
                    cookie_banner: cookieBannerDetected,
                    cookie_banner_text: cookieBannerText,
                    popup_dialog: popupDialog,
                    captcha: captchaDetected,
                    login_wall: loginWall,
                    shadow_dom_count: shadowDomCount,
                    iframes: iframeInfo,
                    iframe_count: iframes.length,
                    aria_live: ariaLive.slice(0, 5),
                    select_options: selectMap,
                    images: images.slice(0, 10),
                    network_requests: networkRequests,
                });
            }""")
            return content
        except Exception as e:
            return json.dumps({"error": str(e), "url": str(self.page.url if self.page else "none")})

    def _parse_page_data(self, page_content: str) -> dict:
        """Extract structured observation from page content for frontend"""
        try:
            data = json.loads(page_content) if page_content.startswith("{") else {}
        except:
            data = {}
        return data

    def _clean_ai_response(self, raw: str) -> str:
        """Strip extended thinking tokens and artifacts from AI response.
        
        MiniMax-M2.7 (and M2.5) may inject thinking/reasoning blocks into
        the visible content even when thinking_params is set to off.
        These appear as:
          - <think_>...</think_> blocks
          - ⋊...⋉ blocks  
          - Content before the first ACTION: that is clearly reasoning
        """
        import re
        text = raw.strip()
        
        # Remove <think thinker>...</think thinker> blocks (MiniMax-M2.7 extended thinking)
        text = re.sub(r'<think thinker>[\\s\\S]*?</think thinker>', '', text)
        
        # Also catch <think_> variant
        text = re.sub(r'<think_>[\\s\\S]*?</think_>', '', text)
        
        # Remove any XML-style thinking blocks
        text = re.sub(r'<thinking>[\\s\\S]*?</thinking>', '', text, flags=re.IGNORECASE)
        
        # Remove Unicode-wrapped thinking blocks (⋀...⋉ or similar)
        text = re.sub(r'⋀[\\s\\S]*?⋉', '', text)
        
        # Remove <thought> tags
        text = re.sub(r'<thought>[\\s\\S]*?</thought>', '', text, flags=re.IGNORECASE)
        
        # If the response contains ACTION: lines, strip everything before the first one
        # (this removes any leaked reasoning that appears before the actions)
        action_match = re.search(r'ACTION:', text)
        if action_match and action_match.start() > 0:
            preamble = text[:action_match.start()].strip()
            # Only strip if the preamble looks like reasoning (no ACTION, multi-line, or contains reasoning keywords)
            reasoning_keywords = ['i need to', 'looking at', 'the page', 'i see', 'i should', 
                                  'let me', 'first,', 'next,', 'i will', 'this appears',
                                  'based on', 'i can see', 'it seems', 'the task']
            if any(kw in preamble.lower() for kw in reasoning_keywords):
                text = text[action_match.start():]
        
        return text.strip()

    def _clean_answer(self, raw_answer: str) -> str:
        """Post-process the final answer to remove AI reasoning artifacts.
        
        Strips MiniMax thinking tokens and preamble patterns.
        """
        import re
        text = raw_answer.strip()
        
        # Remove <think ...>...</think ...> blocks (with closing tag)
        text = re.sub(r'<think[^>]*>.*?</think[^>]*>', '', text, flags=re.DOTALL)
        
        # Remove unclosed <think ...> at start — strip tag + reasoning until first real content
        # MiniMax often opens <think thinker> but never closes it
        think_open = re.match(r'<think[^>]*>\s*', text)
        if think_open:
            after_tag = text[think_open.end():]
            # Find where the actual answer content begins — look for:
            # 1. Numbered list: "1. Something"
            # 2. The word/answer: "The answer is X" or "Answer: X"  
            # 3. A direct statement after a double newline
            answer_start = re.search(
                r'(?:^|\n\s*)(?=\d+\.\s)|(?:The answer is\s)|(?:^Answer:\s)',
                after_tag, re.MULTILINE
            )
            if answer_start:
                text = after_tag[answer_start.start():].lstrip()
            else:
                # Fallback: look for double-newline (reasoning → answer boundary)
                nl_break = re.search(r'\n\s*\n', after_tag)
                if nl_break:
                    text = after_tag[nl_break.end():]
                else:
                    text = after_tag
        
        # Remove common preamble patterns  
        preamble_patterns = [
            r'^(?:Based on|After|From|By|I (?:can see|see|found|noticed|observed|determined)|Looking at|The page (?:shows|displays|contains|has)|Upon (?:examining|reviewing|scrolling))[^.]*\.\s*',
            r'^(?:Here (?:are|is)|The (?:following|top|first)|These (?:are|were))[^:]*:\s*',
        ]
        for pat in preamble_patterns:
            text = re.sub(pat, '', text, flags=re.IGNORECASE).strip()
        
        # Remove trailing reasoning
        text = re.sub(r'\s*(?:Let me|I hope|I believe|This should|Hopefully).*$', '', text, flags=re.IGNORECASE).strip()
        
        # Remove tool call artifacts (MiniMax sometimes emits [TOOL_CALL] blocks)
        text = re.sub(r'\[TOOL_CALL][\s\S]*?$', '', text, flags=re.MULTILINE).strip()
        text = re.sub(r'\[TOOL_CALL]', '', text).strip()

        # Remove done(...) wrapper if the LLM returned it as a raw string
        text = re.sub(r'^done\((.+)\)$', r'\1', text).strip()
        
        # Truncate to 500 chars
        if len(text) > 500:
            text = text[:497] + '...'
        
        return text

    async def _call_ai(self, task: str, page_content: str) -> tuple[str, float, str]:
        """Call AI model to decide next action.
        Returns (ai_response, duration_ms, model_name).
        Retries up to 3 times with exponential backoff on API errors."""
        start = time.monotonic()
        model_name = self.model_name
        api_key = self.api_key

        if not api_key:
            logger.warning("No API key available, using fallback AI")
            return self._fallback_ai(task, page_content), (time.monotonic() - start) * 1000, "fallback"

        # Build messages for this call
        messages = self._build_ai_messages(task, page_content)

        # Use multi-model router
        last_error = None
        for attempt in range(3):
            try:
                from ai_router import call_ai as router_call_ai
                raw_content, duration_ms, provider = await router_call_ai(
                    messages=messages,
                    model_name=model_name,
                    timeout=30.0,
                )
                ai_response = self._clean_ai_response(raw_content)
                self.conversation_history.append({"role": "user", "content": f"Task: {task}\n\nPage state:\n{page_content[:1000]}"})
                self.conversation_history.append({"role": "assistant", "content": ai_response})
                if len(self.conversation_history) > 6:
                    self.conversation_history = self.conversation_history[-6:]
                return ai_response, duration_ms, provider

            except Exception as e:
                last_error = str(e)
                logger.warning(f"AI call failed (attempt {attempt + 1}/3): {last_error}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue

        # All retries exhausted — return fallback with error context so UI can show it
        error_msg = f"API error after 3 retries: {last_error}"
        logger.error(error_msg)
        fallback_response = self._fallback_ai(task, page_content)
        return f"[ERROR: {last_error[:80]}] {fallback_response}", (time.monotonic() - start) * 1000, "error"

    def _fallback_ai(self, task: str, page_content: str) -> str:
        """Rule-based fallback when AI is unavailable"""
        try:
            data = json.loads(page_content) if page_content.startswith("{") else {}
            title = data.get("title", "")
            text = data.get("text", "")

            task_lower = task.lower()

            if "title" in task_lower or "what" in task_lower:
                return f'ACTION: done(The page title is "{title}". Text on page: {text[:200]})'
            if "text" in task_lower or "content" in task_lower or "visible" in task_lower:
                return f'ACTION: done(Visible text: {text[:500]})'
            if "screenshot" in task_lower:
                return "ACTION: screenshot()"
            if "click" in task_lower:
                interactives = data.get("interactives", [])
                if interactives:
                    target = interactives[0]
                    return f'ACTION: click({target["selector"]})'
                return f'ACTION: done(No clickable elements found. Page title: {title})'

            return f'ACTION: done(Page title: "{title}". Content: {text[:300]})'
        except:
            return f'ACTION: done(Could not parse page. Task was: {task})'

    def _parse_actions(self, response: str) -> list[tuple[str, str]]:
        """Parse AI response into list of (action, argument) tuples — supports batching."""
        actions = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("ACTION:"):
                rest = line[7:].strip()
                if "(" in rest and rest.endswith(")"):
                    name = rest[:rest.index("(")].strip()
                    arg = rest[rest.index("(")+1:-1].strip()
                    actions.append((name, arg))
                else:
                    # Bare "done" or "screenshot" etc without parens
                    parts = rest.split(None, 1)
                    if parts:
                        name = parts[0].lower()
                        arg = parts[1] if len(parts) > 1 else ""
                        actions.append((name, arg))
        return actions if actions else [("done", response[:200])]

    def _parse_action(self, response: str) -> tuple[str, str]:
        """Legacy single-action parser — delegates to _parse_actions."""
        actions = self._parse_actions(response)
        return actions[0]

    async def _retry_intelligent(self, action: str, arg: str, error_msg: str) -> tuple[bool, dict]:
        """On action failure, try alternative approaches before giving up.

        Returns (success, result_dict).
        """
        result = {"success": False, "error": error_msg}

        # ── Click failures: try alternate selectors ─────────────────────────────
        if action == "click":
            try:
                # Try JS click as fallback — handle Playwright-specific selectors
                # (:has-text, >>, etc.) by falling back to text-based search
                arg_lower = arg.lower()
                alt_js = f"""
                (function() {{
                    // If selector looks like Playwright-specific, skip to text search
                    var is_playwright_selector = /:has-text|>>|>>=|:text|:visible/.test('{arg}');
                    if (!is_playwright_selector) {{
                        try {{
                            var el = document.querySelector('{arg}');
                            if (el) {{ el.click(); return 'clicked'; }}
                        }} catch(e) {{ /* invalid selector */ }}
                    }}
                    // Text-based search fallback
                    var all = document.querySelectorAll('button, a, [role="button"], input[type="submit"]');
                    for (var i = 0; i < all.length; i++) {{
                        var txt = all[i].textContent.trim().toLowerCase();
                        if (txt.includes('{arg_lower}')) {{
                            all[i].click(); return 'clicked_by_text';
                        }}
                    }}
                    return 'not_found';
                }})();
                """
                js_result = await self.page.evaluate(alt_js)
                if js_result in ("clicked", "clicked_by_text"):
                    await self._human_delay(0.3, 0.8)
                    return True, {"success": True}
            except Exception as js_err:
                logger.warning(f"JS click fallback failed: {js_err}")

        # ── Type failures: try fill with delay, or evaluate ─────────────────
        if action == "type":
            try:
                parts = arg.split(",", 1)
                if len(parts) == 2:
                    selector, text = parts[0].strip(), parts[1].strip()
                    # Remove quotes if present
                    if (text.startswith('"') and text.endswith('"')) or \
                       (text.startswith("'") and text.endswith("'")):
                        text = text[1:-1]
                    # Escape single quotes for JS string
                    text_escaped = text.replace("'", "\\'")
                    js_code = (
                        "(function() {"
                        "var el = document.querySelector('%s');"
                        "if (el) { el.focus(); el.value = '%s'; "
                        "el.dispatchEvent(new Event('input', { bubbles: true })); "
                        "el.dispatchEvent(new Event('change', { bubbles: true })); "
                        "return 'typed'; }"
                        "return 'not_found';"
                        "})();" % (selector, text_escaped)
                    )
                    js_result = await self.page.evaluate(js_code)
                    if js_result == "typed":
                        await self._human_delay(0.3, 0.6)
                        return True, {"success": True}
            except Exception as js_err:
                logger.warning("JS type fallback failed: %s", js_err)

        if action == "check":
            try:
                js_code = (
                    "(function() {"
                    "var el = document.querySelector('%s');"
                    "if (el) { el.checked = true; "
                    "el.dispatchEvent(new Event('change', { bubbles: true })); "
                    "return 'checked'; }"
                    "return 'not_found';"
                    "})();" % arg
                )
                js_result = await self.page.evaluate(js_code)
                if js_result == "checked":
                    await self._human_delay(0.2, 0.5)
                    return True, {"success": True}
            except Exception as js_err:
                logger.warning(f"JS check fallback failed: {js_err}")

        # ── Evaluate failures: try alternate JS approaches ─────────────────────
        if action == "evaluate":
            try:
                # Try wrapping in try-catch and return structured result
                alt_js = f"""
                (function() {{
                    try {{
                        var __result = ({arg});
                        return JSON.stringify({{ok: true, result: __result}});
                    }} catch(e) {{
                        return JSON.stringify({{ok: false, error: e.message}});
                    }}
                }})();
                """
                js_result = await self.page.evaluate(alt_js)
                import json as _json
                parsed = _json.loads(js_result)
                if parsed.get("ok"):
                    await self._human_delay(0.2, 0.5)
                    return True, {"success": True, "answer": str(parsed.get("result", ""))[:500]}
                else:
                    # Try simpler eval without IIFE wrapping
                    simple_result = await self.page.evaluate(arg)
                    await self._human_delay(0.2, 0.5)
                    return True, {"success": True, "answer": str(simple_result)[:500]}
            except Exception as js_err:
                logger.warning(f"JS evaluate fallback failed: {js_err}")

        return False, result

    async def _execute_action(self, action: str, arg: str) -> dict:
        """Execute a single browser action"""
        result = {"action": action, "arg": arg, "success": False, "error": None, "selector": arg}

        try:
            if action == "navigate":
                await self.action_history.capture_snapshot(action)
                url = arg if arg.startswith("http") else f"https://{arg}"

                # T031: Apply site-specific antibot override BEFORE navigation
                override = get_override_for_url(url)
                if override:
                    applied = await apply_site_override(self.page, override)
                    if applied:
                        logger.info(f"[SiteOverride] Applied {override.name} bypass for {url}")

                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await self._human_delay(0.5, 1.5)

                # T031: Post-navigation delay + JS for known hard sites
                if override and override.post_nav_delay > 0:
                    await asyncio.sleep(override.post_nav_delay)
                if override and override.post_nav_js:
                    try:
                        await self.page.evaluate(override.post_nav_js)
                    except Exception as e:
                        logger.warning(f"[SiteOverride] post_nav_js failed: {e}")

                result["success"] = True
                result["url"] = self.page.url
                self.action_history.record_action(action, {"url": arg}, "completed", "navigated")

            elif action == "click":
                await self.action_history.capture_snapshot(action)
                # Move mouse naturally to element before clicking
                try:
                    el = await self.page.query_selector(arg)
                    if el:
                        box = await el.bounding_box()
                        if box:
                            cx = int(box["x"] + box["width"] * random.uniform(0.35, 0.65))
                            cy = int(box["y"] + box["height"] * random.uniform(0.35, 0.65))
                            await self._human_move(cx, cy)
                except Exception:
                    pass  # proceed without pre-move on any error
                try:
                    # Use commit to avoid hanging on button clicks that don't navigate
                    await self.page.click(arg, timeout=5000)
                    await self._human_delay(0.3, 1.0)
                    result["success"] = True
                except Exception as e:
                    clicked = False
                    try:
                        submit_texts = ["submit", "submit order", "submit"]
                        for text in submit_texts:
                            btns = await self.page.query_selector_all("button, input[type='submit'], [type='submit']")
                            for btn in btns:
                                btn_text = (await btn.inner_text()).lower().strip()
                                btn_type = await btn.get_attribute("type") or ""
                                if text in btn_text or btn_type == "submit":
                                    await btn.click()
                                    await self._human_delay(0.3, 1.0)
                                    result["success"] = True
                                    clicked = True
                                    break
                            if clicked:
                                break
                    except:
                        pass
                    if not clicked:
                        try:
                            await self.page.click(arg, timeout=8000)
                            await self._human_delay(0.3, 1.0)
                            result["success"] = True
                        except:
                            result["error"] = f"Click failed for '{arg}': {str(e)[:80]}"
                            result["success"] = False
                if result["success"]:
                    self.action_history.record_action("click", {"selector": arg}, "completed", "clicked")
                else:
                    self.action_history.record_action("click", {"selector": arg}, "failed", result.get("error", "unknown"))

            elif action == "type":
                await self.action_history.capture_snapshot(action)
                parts = arg.split(",", 1)
                if len(parts) == 2:
                    selector, text = parts[0].strip(), parts[1].strip()
                    if (text.startswith('"') and text.endswith('"')) or \
                       (text.startswith("'") and text.endswith("'")):
                        text = text[1:-1]
                    try:
                        await self._human_type(selector, text)
                    except Exception:
                        # Fallback: instant fill if human-type fails
                        await self.page.fill(selector, text, no_wait_after=True)
                    await self._human_delay(0.15, 0.4)
                    result["success"] = True
                    self.action_history.record_action("type", {"selector": selector, "text": text[:50]}, "completed", "typed")
                else:
                    result["error"] = "Invalid type format: use selector, text"
                    self.action_history.record_action("type", {"arg": arg}, "failed", result["error"])

            elif action == "check":
                await self.action_history.capture_snapshot(action)
                try:
                    # no_wait_after to avoid hanging on elements that don't trigger network changes
                    await self.page.check(arg, timeout=5000, no_wait_after=True)
                    await self._human_delay(0.1, 0.3)
                    result["success"] = True
                    self.action_history.record_action("check", {"selector": arg}, "completed", "checked")
                except Exception as e:
                    try:
                        await self.page.click(arg, timeout=5000)
                        await self._human_delay(0.1, 0.3)
                        result["success"] = True
                        self.action_history.record_action("check", {"selector": arg}, "completed", "checked_via_click")
                    except:
                        result["error"] = f"Check failed for '{arg}': {str(e)[:80]}"
                        result["success"] = False
                        self.action_history.record_action("check", {"selector": arg}, "failed", result["error"])

            elif action == "select":
                # Proper <select> interaction — open dropdown then pick option by text
                try:
                    parts = arg.rsplit(",", 1)
                    if len(parts) == 2:
                        # format: "select[name=size], large" — select by option text
                        sel, opt_text = parts[0].strip(), parts[1].strip()
                        await self.page.click(sel)
                        await asyncio.sleep(0.2)
                        # Click option by text match
                        opt_xpath = f"//option[contains(text(),'{opt_text}')]"
                        await self.page.click(f"{sel} >> xpath={opt_xpath}", timeout=3000)
                    else:
                        # Just a selector — click to open the dropdown
                        await self.page.click(arg)
                    await self._human_delay(0.1, 0.3)
                    result["success"] = True
                except Exception as e:
                    # Fallback: try native select_option
                    try:
                        el = await self.page.query_selector(arg)
                        if el and el.get_attribute("tagName", "").lower() == "select":
                            await el.select_option(arg)
                        else:
                            await self.page.click(arg)
                        await self._human_delay(0.1, 0.3)
                        result["success"] = True
                    except Exception:
                        result["error"] = f"select failed: {str(e)[:80]}"

            elif action == "select_option":
                await self.action_history.capture_snapshot(action)
                # arg format: "selector, value" OR "selector, label=text"
                parts = arg.rsplit(",", 1)
                if len(parts) == 2:
                    selector = parts[0].strip()
                    raw_value = parts[1].strip()
                    try:
                        el = await self.page.query_selector(selector)
                        if el:
                            # Check for label=text syntax
                            if raw_value.startswith("label="):
                                label_text = raw_value[6:].strip()
                                await el.select_option(label=label_text)
                            else:
                                # Try value match first; if no options found, try label match
                                try:
                                    await el.select_option(raw_value)
                                except Exception as val_err:
                                    # Fallback: try matching by visible text via XPath
                                    await el.select_option(label=raw_value)
                            await self._human_delay(0.1, 0.3)
                            result["success"] = True
                            self.action_history.record_action("select_option", {"selector": selector, "value": raw_value}, "completed", "selected")
                        else:
                            result["error"] = f"No <select> found at {selector}"
                            self.action_history.record_action("select_option", {"arg": arg}, "failed", result["error"])
                    except Exception as e:
                        result["error"] = f"select_option failed: {str(e)[:80]}"
                        self.action_history.record_action("select_option", {"arg": arg}, "failed", result["error"])
                else:
                    result["error"] = "Invalid select_option format: use selector, value"
                    self.action_history.record_action("select_option", {"arg": arg}, "failed", result["error"])

            elif action == "hover":
                await self.action_history.capture_snapshot(action)
                try:
                    await self.page.hover(arg, timeout=5000)
                    await self._human_delay(0.2, 0.5)
                    result["success"] = True
                    self.action_history.record_action("hover", {"selector": arg}, "completed", "hovered")
                except Exception as e:
                    result["error"] = f"Hover failed: {str(e)[:80]}"
                    self.action_history.record_action("hover", {"selector": arg}, "failed", result["error"])

            elif action == "dblclick":
                await self.action_history.capture_snapshot(action)
                try:
                    await self.page.dblclick(arg, timeout=5000)
                    await self._human_delay(0.3, 0.8)
                    result["success"] = True
                    self.action_history.record_action("dblclick", {"selector": arg}, "completed", "dblclicked")
                except Exception as e:
                    result["error"] = f"dblclick failed: {str(e)[:80]}"
                    self.action_history.record_action("dblclick", {"selector": arg}, "failed", result["error"])

            elif action == "switch_to_tab":
                try:
                    idx = int(arg)
                    pages = self.context.pages
                    if 0 <= idx < len(pages):
                        await pages[idx].bring_to_front()
                        self.page = pages[idx]
                        await self._human_delay(0.3, 0.6)
                        result["success"] = True
                    else:
                        result["error"] = f"Tab index {idx} out of range (have {len(pages)} tabs)"
                except Exception as e:
                    result["error"] = f"switch_to_tab failed: {str(e)[:80]}"

            elif action == "open_tab":
                # arg: optional URL to open in new tab
                url = arg.strip() if arg else "about:blank"
                try:
                    new_page = await self.context.new_page()
                    if url != "about:blank":
                        await new_page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    self.page = new_page
                    await self._human_delay(0.2, 0.5)
                    result["success"] = True
                    result["url"] = new_page.url
                except Exception as e:
                    result["error"] = f"open_tab failed: {str(e)[:80]}"

            elif action == "close_tab":
                try:
                    pages = self.context.pages
                    current_idx = pages.index(self.page) if self.page in pages else -1
                    await self.page.close()
                    remaining = [p for p in pages if not p.is_closed()]
                    if remaining:
                        self.page = remaining[0]
                        await self.page.bring_to_front()
                    else:
                        # No tabs left — create a blank one
                        self.page = await self.context.new_page()
                    result["success"] = True
                    result["remaining_tabs"] = len(remaining)
                except Exception as e:
                    result["error"] = f"close_tab failed: {str(e)[:80]}"

            elif action == "get_text":
                try:
                    el = await self.page.query_selector(arg)
                    if el:
                        text = (await el.inner_text())[:500]
                        result["success"] = True
                        result["answer"] = text
                    else:
                        result["error"] = f"No element found at {arg}"
                except Exception as e:
                    result["error"] = f"get_text failed: {str(e)[:80]}"

            elif action == "evaluate":
                try:
                    js_result = await self.page.evaluate(arg)
                    result["success"] = True
                    result["answer"] = str(js_result)[:500]
                except Exception as e:
                    result["error"] = f"evaluate failed: {str(e)[:80]}"

            elif action == "submit":
                await self.action_history.capture_snapshot(action)
                # Use a short wait so we don't hang waiting for a POST response
                # that doesn't navigate anywhere (e.g. httpbin.org/post)
                try:
                    await asyncio.wait_for(
                        self.page.click(arg),
                        timeout=15.0
                    )
                except asyncio.TimeoutError:
                    # Fallback: just click without waiting
                    try:
                        await self.page.click(arg, timeout=8000)
                    except Exception:
                        pass
                await self._human_delay(0.5, 1.5)
                result["success"] = True
                self.action_history.record_action("submit", {"selector": arg}, "completed", "submitted")

            elif action == "scroll":
                await self.action_history.capture_snapshot(action)
                amount = random.randint(300, 700)
                direction = amount if arg == "down" else -amount
                await self.page.mouse.wheel(0, direction)
                await self._human_delay(0.3, 0.8)
                result["success"] = True
                self.action_history.record_action("scroll", {"direction": arg}, "completed", "scrolled")

            elif action == "wait":
                seconds = min(float(arg), 10)
                await asyncio.sleep(seconds)
                result["success"] = True

            elif action == "screenshot":
                result["success"] = True
                result["screenshot"] = True

            elif action == "done":
                result["success"] = True
                result["answer"] = arg

        except Exception as e:
            result["error"] = str(e)[:200]

        return result

    async def undo_last_action(self) -> dict:
        """Public method: undo the last undoable browser action."""
        return await self.action_history.undo_last()

    async def _take_screenshot(self) -> str:
        """Take screenshot and return base64 (JPEG, max ~200KB to fit WebSocket frame limits)"""
        if self.page:
            try:
                # Use JPEG for compression (10x smaller than PNG), cap to ~200KB base64
                ss = await asyncio.wait_for(
                    self.page.screenshot(type="jpeg", quality=70, full_page=False,
                                         timeout=10.0),
                    timeout=12.0
                )
                b64 = base64.b64encode(ss).decode()
                # WebSocket frame default max is 1MB; keep well under with other JSON fields
                if len(b64) > 800_000:
                    # Downscale further
                    import io
                    from PIL import Image
                    img = Image.open(io.BytesIO(ss))
                    img.thumbnail((1024, 768), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=60)
                    b64 = base64.b64encode(buf.getvalue()).decode()
                return b64
            except asyncio.TimeoutError:
                return ""
            except Exception:
                return ""
        return ""

    async def stream_execute(self, task: str, url: str, mode: str) -> AsyncGenerator[dict, None]:
        """Stream step-by-step execution via WebSocket — FULL rich step data"""
        await self._init_browser()

        steps_executed = 0

        # Mode-based step limits
        mode_limits = {"fast": 12, "standard": 20, "deep": 30}
        max_steps = mode_limits.get(mode.lower(), mode_limits.get("fast", 15))
        max_total_actions = max_steps * 4  # Hard cap on total actions (each step can have multiple batched actions)

        # Navigate to start
        nav_start = time.monotonic()
        try:
            # Try primary navigation strategy
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as nav_err:
                # Retry with more relaxed waiting
                logger.warning(f"Primary nav failed ({nav_err}), retrying with load strategy")
                await self.page.goto(url, wait_until="load", timeout=45000)
            # BUG-02 fix: dismiss any CAPTCHA iframes after initial navigation
            captcha_domain = await self._dismiss_captcha_iframe()
            if captcha_domain:
                logger.info(f"CAPTCHA iframe detected after navigation — dismissed {captcha_domain}")
                # T010: attempt solve
                try:
                    await self._handle_captcha_iframe()
                except Exception:
                    pass
            captcha_wait_count = 0   # BUG-05 fix: track consecutive wait()s for CAPTCHA loops
            consecutive_failures = 0  # Track consecutive step failures — bail after 3
            steps_executed += 1
            nav_ms = int((time.monotonic() - nav_start) * 1000)
            self._save_step({"step": steps_executed, "action": "navigate", "status": "completed", "screenshot": None})
            yield {
                "step": steps_executed,
                "action": "navigate",
                "argument": url,
                "status": "completed",
                "url": self.page.url,
                "page_title": await self.page.title() if self.page else "",
                "duration_ms": nav_ms,
                "model": "playwright",
                "screenshot": await self._take_screenshot(),
                "observation": f"Loaded {url}",
            }
        except Exception as e:
            yield {
                "step": 0, "action": "error", "error": f"Navigation failed: {str(e)}",
                "status": "failed", "duration_ms": int((time.monotonic() - nav_start) * 1000),
            }
            return

        for step_num in itertools.count(start=2):
            if step_num > max_steps + 1:  # +1 because step 1 is navigation
                break
            # Get page state
            page_content = await self._get_page_content()
            page_data = self._parse_page_data(page_content)
            page_title_val = await self.page.title() if self.page else ""
            page_url = page_data.get("url", "")

            # T027 + T030: Check route interceptor for mid-session challenge detection
            # If a challenge was detected mid-session, escalate to tier retry
            if self._route_interceptor and self._route_interceptor.should_escalate(page_url):
                logger.warning(
                    f"[ChallengeEscalation] Challenge detected on {self._route_interceptor.get_domain_key(page_url)} "
                    f"during step {step_num} — signaling tier fallback"
                )
                challenge_info = self._route_interceptor.get_domain_challenge(page_url)
                challenge_type_str = challenge_info.challenge_type.value if challenge_info else "unknown"
                yield {
                    "step": step_num,
                    "action": "challenge_escalate",
                    "argument": self._challenge_domain or page_url,
                    "status": "thinking",
                    "url": page_url,
                    "page_title": page_title_val,
                    "model": "playwright",
                    "engine": self._browser_engine,
                    "duration_ms": 0,
                    "ai_reasoning": f"Anti-bot challenge ({challenge_type_str}) detected mid-session. Escalating to higher tier.",
                    "observation": f"Challenge detected: {challenge_type_str}. Consider switching to a more stealthy browser engine or using proxy rotation.",
                    "screenshot": await self._take_screenshot(),
                    "challenge_type": challenge_type_str,
                }
                # Reset escalation flag so we don't re-yield the same challenge
                self._challenge_escalation = False
                # NOTE: Actual tier switching requires session restart. The AI will
                # see this step and can decide to retry or change strategy.

            # Build observation summary for frontend
            form_fields = list(page_data.get("form", {}).keys())
            interactives = page_data.get("interactives", [])
            buttons = [i["text"] or i["selector"] for i in interactives if i["tag"] in ("button", "a") or i["type"] in ("submit", "button")]

            observation_parts = []
            if form_fields:
                observation_parts.append(f"Forms: {', '.join(form_fields[:8])}")
            if buttons:
                observation_parts.append(f"Buttons: {', '.join(buttons[:6])}")
            if page_title_val:
                observation_parts.append(f"Title: {page_title_val}")
            observation = " | ".join(observation_parts) or f"Page at {page_url}"

            # Call AI
            ai_response, ai_ms, model_name = await self._call_ai(task, page_content)

            # If API failed after all retries, surface error and stop
            if model_name == "error":
                yield {
                    "step": step_num,
                    "action": "error",
                    "argument": "",
                    "status": "failed",
                    "url": page_url,
                    "page_title": page_title_val,
                    "model": "error",
                    "duration_ms": int(ai_ms),
                    "ai_reasoning": ai_response,
                    "observation": f"API error: {ai_response[:200]}",
                    "screenshot": await self._take_screenshot(),
                    "error": ai_response[:200],
                }
                return

            action, arg = self._parse_action(ai_response)
            # Always parse all actions for batching support
            all_actions = self._parse_actions(ai_response)

            # Send ONE thinking step showing all planned actions
            yield {
                "step": step_num,
                "action": all_actions[0][0],
                "argument": all_actions[0][1][:150] if all_actions[0][1] else "",
                "status": "thinking",
                "url": page_url,
                "page_title": page_title_val,
                "model": model_name, "engine": self._browser_engine,
                "duration_ms": int(ai_ms),
                "ai_reasoning": ai_response,
                "observation": observation,
                "screenshot": None,
                "thinking": (
                    f"[{model_name} · {ai_ms:.0f}ms]\n"
                    f"Looking at: {page_title_val}\n"
                    f"Task: {task[:80]}{'...' if len(task) > 80 else ''}\n"
                    f"Observation: {observation[:200]}\n"
                    f"Decision:\n" + "\n".join(f"  {i+1}. {a[0]}({a[1][:80]})" for i, a in enumerate(all_actions))
                ),
            }

            # Execute all actions in sequence
            for batch_idx, (action, arg) in enumerate(all_actions):
                # Hard cap: stop if total actions exceed limit
                if steps_executed >= max_total_actions:
                    yield {
                        "step": step_num, "action": "done",
                        "argument": f"Reached total action limit ({max_total_actions}). Task may need more steps.",
                        "status": "completed",
                        "url": self.page.url if self.page else page_url,
                        "page_title": await self.page.title() if self.page else page_title_val,
                        "duration_ms": 0, "model": model_name, "engine": self._browser_engine,
                        "observation": f"Action limit reached after {steps_executed} total actions.",
                        "screenshot": await self._take_screenshot(),
                        "answer": f"Task incomplete — reached action limit ({max_total_actions}). The page was too complex for the allowed steps.",
                    }
                    return
                exec_start = time.monotonic()

                # BUG-02 fix: before EVERY action, check for CAPTCHA iframes and try to solve.
                captcha_domain = await self._dismiss_captcha_iframe()
                if captcha_domain:
                    logger.info(f"CAPTCHA iframe detected during {action} — dismissed {captcha_domain}")
                    # T010: attempt solve (API key may be available)
                    try:
                        solved = await self._handle_captcha_iframe()
                        if solved:
                            logger.info(f"CAPTCHA solved during {action} — continuing")
                    except Exception as e:
                        logger.warning(f"CAPTCHA solve attempt failed: {e}")

                # T011: take before-screenshot for visual diffing
                before_ss = await self._take_screenshot()

                try:
                    result = await asyncio.wait_for(
                        self._execute_action(action, arg),
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    result = {"success": False, "error": f"Step timed out after 30s (action: {action})"}
                exec_ms = int((time.monotonic() - exec_start) * 1000)

                # T011: compute visual diff after every successful action
                diff_info = {}
                retry_for_no_change = False
                if result["success"] and before_ss and action not in ("screenshot", "done", "wait"):
                    try:
                        from visual_diff import pixels_changed
                        after_ss = await self._take_screenshot()
                        pct, dtype, dinfo = pixels_changed(before_ss, after_ss)
                        diff_info = {
                            "diff_pct":     round(pct * 100, 2),
                            "diff_type":    dtype,
                            "diff_significant": pct >= 0.05,
                        }
                        result["_visual_diff"] = diff_info
                        # T011: no visual change → wait then retry same action once
                        if dtype in ("none", "minimal"):
                            retry_for_no_change = True
                    except Exception:
                        pass  # diff is best-effort

                # T011: no visual change → wait 1.5s then re-check
                if retry_for_no_change:
                    await asyncio.sleep(1.5)
                    after_ss = await self._take_screenshot()
                    pct2, dtype2, _ = pixels_changed(before_ss, after_ss)
                    if dtype2 in ("none", "minimal"):
                        await asyncio.sleep(2.0)
                        retry_ss = await self._take_screenshot()
                        pct3, dtype3, _ = pixels_changed(before_ss, retry_ss)
                        if dtype3 in ("none", "minimal"):
                            observation = (f"[No visual change after {action}] "
                                          f"Page may be blocked or action had no effect. "
                                          f"Proceeding anyway — diff_type={dtype3}, pct={round(pct3*100,2)}%")

                # If this is get_text or evaluate, carry the answer through
                answer_val = result.get("answer", "")

                if result["success"]:
                    # BUG-05 fix: track consecutive wait()s; bail after 3 with CAPTCHA clear message
                    if action == "wait":
                        captcha_wait_count += 1
                        if captcha_wait_count >= 3:
                            yield {
                                "step": step_num,
                                "action": "done",
                                "argument": f"Stopped: CAPTCHA/site protection detected after {captcha_wait_count} consecutive wait() attempts.",
                                "status": "completed",
                                "url": self.page.url if self.page else page_url,
                                "page_title": await self.page.title() if self.page else page_title_val,
                                "duration_ms": exec_ms,
                                "model": model_name, "engine": self._browser_engine,
                                "ai_reasoning": f"CAPTCHA loop detected: {captcha_wait_count} consecutive wait() calls with no page progress. Giving up with a clear message.",
                                "observation": f"CAPTCHA blocker detected after {captcha_wait_count} wait attempts.",
                                "screenshot": await self._take_screenshot(),
                                "answer": "CAPTCHA detected — site is blocking automation. Consider using stealth mode or a different target.",
                            }
                            return
                    else:
                        captcha_wait_count = 0   # reset on non-wait action
                    consecutive_failures = 0  # Reset — this step succeeded
                    steps_executed += 1

                    if action == "done":
                        # ── Record successful task in domain memory ──────────────────
                        try:
                            from domain_memory import learn_from_completed_task
                            from urllib.parse import urlparse
                            if self.page:
                                url = self.page.url
                                domain = urlparse(url).netloc if url else ""
                                if domain:
                                    learn_from_completed_task(
                                        domain=domain,
                                        url=url,
                                        task=task,
                                        successful_selectors=self.action_history.successful_selectors[-20:],
                                        action_steps=[a for a, _ in self.action_history.history[-20:]]
                                    )
                        except Exception:
                            pass  # Domain memory is best-effort

                        yield {
                            "step": step_num,
                            "action": "done",
                            "argument": answer_val or arg,
                            "status": "completed",
                            "url": self.page.url if self.page else page_url,
                            "page_title": await self.page.title() if self.page else page_title_val,
                            "duration_ms": exec_ms,
                            "model": model_name, "engine": self._browser_engine,
                            "ai_reasoning": ai_response,
                            "observation": observation,
                            "screenshot": await self._take_screenshot(),
                            "answer": self._clean_answer(answer_val or arg),
                        }
                        return
                    elif result.get("screenshot"):
                        pass

                    # Send SUCCESS snapshot for this action
                    screenshot = await self._take_screenshot()
                    yield {
                        "step": step_num,
                        "action": action,
                        "argument": arg[:150] if arg else "",
                        "status": "completed",
                        "url": self.page.url if self.page else page_url,
                        "page_title": await self.page.title() if self.page else page_title_val,
                        "duration_ms": exec_ms,
                        "model": model_name, "engine": self._browser_engine,
                        "ai_reasoning": ai_response,
                        "observation": observation,
                        "screenshot": screenshot,
                        "error": None,
                        "visual_diff": diff_info if diff_info else None,
                    }

                    # If get_text/evaluate, surface the extracted value in observation
                    # Only take screenshot if the page actually changed (not for pure reads)
                    if answer_val:
                        pass  # skip extra screenshot for read-only actions
                else:
                    # ── Retry intelligence ─────────────────────────────────────────
                    retry_success = False
                    if not result["success"]:
                        error_msg = result.get("error", "")
                        retry_success, retry_result = await self._retry_intelligent(action, arg, error_msg)
                        if retry_success:
                            result = retry_result

                    if not retry_success:
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            yield {
                                "step": step_num,
                                "action": "done",
                                "argument": f"Stopping after {consecutive_failures} consecutive failures. The site may be blocking automation.",
                                "status": "completed",
                                "url": self.page.url if self.page else page_url,
                                "page_title": await self.page.title() if self.page else page_title_val,
                                "duration_ms": exec_ms,
                                "model": model_name, "engine": self._browser_engine,
                                "observation": f"Bailed after {consecutive_failures} consecutive failures.",
                                "screenshot": await self._take_screenshot(),
                                "answer": f"Could not complete task — {consecutive_failures} consecutive action failures. The site may have bot protection or complex interactive elements.",
                            }
                            return
                        yield {
                            "step": step_num,
                            "action": "error",
                            "argument": arg[:150] if arg else "",
                            "status": "retrying",
                            "url": page_url,
                            "page_title": page_title_val,
                            "duration_ms": exec_ms,
                            "model": model_name, "engine": self._browser_engine,
                            "ai_reasoning": ai_response,
                            "observation": observation,
                            "screenshot": await self._take_screenshot(),
                            "error": result.get("error", "Unknown error"),
                            "retry_count": 1,
                        }
                        # Stop execution of remaining batch actions on failure
                        break

                # Small human delay between batched actions
                await self._human_delay(0.3, 0.8)

        # Max steps reached
        yield {
            "step": steps_executed,
            "action": "done",
            "argument": f"Reached step limit ({steps_executed} steps executed). Current page: {self.page.url if self.page else 'unknown'}",
            "status": "completed",
            "url": self.page.url if self.page else "",
            "page_title": await self.page.title() if self.page else "",
            "duration_ms": 0,
            "model": model_name, "engine": self._browser_engine,
            "screenshot": await self._take_screenshot(),
        }

    # ── Session persistence (Phase 2) ──────────────────────────────────────────
    async def save_session(self, name: str) -> dict:
        """Save current browser state as a named session via SessionManager."""
        return await self.session_manager.save_session(name)

    async def load_session(self, name: str) -> dict:
        """Restore browser state from a named session via SessionManager."""
        return await self.session_manager.load_session(name)

    # ── Credential Vault (Phase 5) ────────────────────────────────────────────
    async def fill_from_vault(self, domain: str) -> Optional[dict]:
        """
        Use vault credential to fill login form. Called by MCP tools.
        Returns username + password + TOTP for direct page injection.
        Uses httpx.AsyncClient so it never blocks the event loop.
        """
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"http://localhost:8001/api/vault/fill/{domain}")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.warning(f"fill_from_vault({domain}) failed: {e}")
        return None

    async def cleanup(self):
        """Clean up all resources. Optionally save session if session_name is set."""
        # Auto-save session on cleanup if name is set (Phase 2)
        if self.session_name and self.active_session_name is None:
            try:
                await self.session_manager.save_session(self.session_name)
                logger.info(f"Session '{self.session_name}' auto-saved on cleanup")
            except Exception as e:
                logger.warning(f"Failed to auto-save session '{self.session_name}': {e}")

        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except Exception:
            pass
        self.page = None

        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        self.context = None

        try:
            if self._camoufox_ctx is not None:
                await self._camoufox_ctx.__aexit__(None, None, None)
            elif self._nodriver_bridge is not None:
                # T036: nodriver bridge — calls Playwright close + nodriver browser stop
                await self._nodriver_bridge.stop()
            elif self.browser:
                await self.browser.close()
        except Exception:
            pass
        self.browser = None
        self._camoufox_ctx = None

        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.playwright = None
