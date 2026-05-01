"""
tls_fingerprint.py — TLS/SSL fingerprint generation and manipulation.

Provides JA3/JA4 fingerprint synthesis, TLS extension randomization,
and realistic browser-like TLS ClientHello generation.

JA3:   MD5 hash of concatenated TLS ClientHello fields (version, ciphers, extensions, etc.)
JA4:   Sha256 fingerprint in format t13d1516h2_... (more readable than JA3)

References:
  - JA3 spec: https://github.com/salesforce/ja3
  - JA4 spec: https://github.com/FoxIO-LLC/ja4
  - TLS 1.3 cipher suites: https://www.iana.org/assignments/tls-parameters/tls-parameters.xhtml
"""
import hashlib
import random
import struct
from typing import List, Optional, Tuple


# ── TLS version constants ──────────────────────────────────────────────────────
TLS_1_0 = 0x0301
TLS_1_1 = 0x0302
TLS_1_2 = 0x0303
TLS_1_3 = 0x0304

# ── Realistic browser cipher suite pools ──────────────────────────────────────

# Chrome 136 (Windows) — strong ordering, TLS 1.3 first
CHROME_136_WINDOWS_CIPHERS = [
    # TLS 1.3 (RFC 8448 order)
    0x1301,  # TLS_AES_128_GCM_SHA256
    0x1302,  # TLS_AES_256_GCM_SHA384
    0x1303,  # TLS_CHACHA20_POLY1305_SHA256
    # TLS 1.2 GCM
    0xc02c,  # ECDHE-ECDSA-AES256-GCM-SHA384
    0xc02b,  # ECDHE-ECDSA-AES128-GCM-SHA256
    0xc024,  # ECDHE-ECDSA-AES256-SHA384
    0xc023,  # ECDHE-ECDSA-AES128-SHA256
    0xc028,  # ECDHE-RSA-AES256-GCM-SHA384
    0xc027,  # ECDHE-RSA-AES128-GCM-SHA256
    0xc00a,  # ECDHE-RSA-AES256-SHA
    0xc009,  # ECDHE-RSA-AES128-SHA
    # TLS 1.2 CBC
    0x009d,  # RSA-WITH-AES256-SHA
    0x003d,  # RSA-WITH-AES128-SHA
]

# Chrome 136 (macOS) — slightly different order
CHROME_136_MACOS_CIPHERS = [
    0x1301, 0x1302, 0x1303,
    0xc02c, 0xc02b, 0xc024, 0xc023,
    0xc028, 0xc027, 0xc00a, 0xc009,
    0x009d, 0x003d,
]

# Firefox 136 (Windows) — different ordering
FIREFOX_136_WINDOWS_CIPHERS = [
    0x1301, 0x1302, 0x1303,  # TLS 1.3
    0xc02c, 0xc02b, 0xc024, 0xc023,  # ECDHE ECDSA
    0xc028, 0xc027, 0xc00a, 0xc009,  # ECDHE RSA
    0x003d,  # RSA-AES128-SHA
    0x009d,  # RSA-AES256-SHA
    0x002f,  # RSA-AES128-SHA
    0xc00a, 0xc009,
]

# Safari 18 (macOS) — Apple protocol ordering
SAFARI_18_MACOS_CIPHERS = [
    0x1301, 0x1302, 0x1303,
    0xc02c, 0xc02b, 0xc030,  # Apple sends these
    0xc028, 0xc027,
    0x009d, 0x003d, 0x002f,
]


# ── TLS extension pools ───────────────────────────────────────────────────────

# Chrome 136 extensions (in order)
CHROME_EXTENSIONS = [
    0x0000,  # server_name (SNI)
    0x000a,  # supported_versions (TLS 1.3)
    0x000b,  # status_request (OCSP staple)
    0x0023,  # session_ticket (deprecated but still sent)
    0x000d,  # signature_algorithms
    0x0017,  # status_request_v2 (OCSP)
    0x0010,  # alpn (h2, http/1.1)
    0x0005,  # status_request (server config?)
    0x001b,  # padding
    0xff01,  # renegotiation_info
]

# Firefox extensions
FIREFOX_EXTENSIONS = [
    0x0000,  # server_name
    0x000a,  # supported_versions
    0x000d,  # signature_algorithms
    0x0010,  # alpn
    0x000b,  # status_request
    0x0017,  # status_request_v2
    0x0023,  # session_ticket
    0xff01,  # renegotiation_info
]

# Safari extensions
SAFARI_EXTENSIONS = [
    0x0000,  # server_name
    0x000a,  # supported_versions
    0x000b,  # status_request
    0x0010,  # alpn
    0x000d,  # signature_algorithms
    0x0017,  # status_request_v2
    0x0023,  # session_ticket
    0xff01,  # renegotiation_info
]


# ── Elliptic curves (TLS named groups) ────────────────────────────────────────

CHROME_GROUPS = [0x001d, 0x0017, 0x001e, 0x0019]  # x25519, secp256r1, secp384r1, brainpoolP256r1
FIREFOX_GROUPS = [0x001d, 0x0017, 0x001e]           # x25519, secp256r1, secp384r1


# ── Signature algorithms ─────────────────────────────────────────────────────

CHROME_SIGALGS = [
    0x0804,  # rsa_pkcs1_sha256
    0x0805,  # rsa_pkcs1_sha384
    0x0806,  # rsa_pkcs1_sha512
    0x0403,  # ecdsa_secp256r1_sha256
    0x0503,  # ecdsa_secp384r1_sha384
    0x0603,  # ecdsa_secp521r1_sha512
    0x0804,  # rsa_pkcs1_sha256
    0x0807,  # sha256dsa
    0x0201,  # md5sha
    0x0301,  # sha1
    0x0401,  # sha224
]


# ── ALPN protocol lists ──────────────────────────────────────────────────────

ALPN_H2 = b"\x02h2\x08http/1.1"      # Chrome
ALPN_H2C = b"\x05h2c\x08http/1.1"    # some servers


# ── Fingerprint profile definitions ─────────────────────────────────────────

BROWSER_PROFILES = {
    "chrome_win": {
        "ciphers": CHROME_136_WINDOWS_CIPHERS,
        "extensions": CHROME_EXTENSIONS,
        "groups": CHROME_GROUPS,
        "sigalgs": CHROME_SIGALGS,
        "alpn": ALPN_H2,
        "version": TLS_1_3,
        "has_psk": False,
        "padding": True,
    },
    "chrome_mac": {
        "ciphers": CHROME_136_MACOS_CIPHERS,
        "extensions": CHROME_EXTENSIONS,
        "groups": CHROME_GROUPS,
        "sigalgs": CHROME_SIGALGS,
        "alpn": ALPN_H2,
        "version": TLS_1_3,
        "has_psk": False,
        "padding": True,
    },
    "firefox_win": {
        "ciphers": FIREFOX_136_WINDOWS_CIPHERS,
        "extensions": FIREFOX_EXTENSIONS,
        "groups": FIREFOX_GROUPS,
        "sigalgs": CHROME_SIGALGS,
        "alpn": ALPN_H2,
        "version": TLS_1_3,
        "has_psk": False,
        "padding": False,
    },
    "safari_mac": {
        "ciphers": SAFARI_18_MACOS_CIPHERS,
        "extensions": SAFARI_EXTENSIONS,
        "groups": [0x001d, 0x0017, 0x001e, 0x0019],
        "sigalgs": CHROME_SIGALGS,
        "alpn": ALPN_H2,
        "version": TLS_1_3,
        "has_psk": False,
        "padding": False,
    },
}


# ── JA3 hash generation ────────────────────────────────────────────────────────

def _cipher_suite_list(cipher_ints: List[int]) -> str:
    """Convert list of TLS cipher suite ints to JA3-formatted string."""
    return "-".join(f"{c:04x}" for c in cipher_ints)


def _extension_list(ext_ints: List[int]) -> str:
    """Convert list of TLS extension IDs to JA3-formatted string."""
    return "-".join(f"{e:04x}" for e in ext_ints)


def _int_to_2byte_list(values: List[int]) -> str:
    """Convert list of ints to JA3-formatted 2-byte values."""
    return "-".join(f"{v:04x}" for v in values)


def _build_ja3_tlssignature(values: List[int]) -> str:
    return "-".join(f"{v:04x}" for v in values)


def generate_ja3(
    cipher_suites: List[int],
    extensions: List[int],
    extension_map: dict,
    elliptic_curves: List[int],
    elliptic_curve_point_formats: List[int],
    tls_version: int = TLS_1_3,
    sigalgs: Optional[List[int]] = None,
) -> Tuple[str, str]:
    """
    Generate JA3 + JA3S (server-side fingerprint) strings.

    JA3 = TLS_version + cipher_suites + extensions + elliptic_curves +
          elliptic_curve_point_formats + sigalgs

    Returns (ja3_digest, ja3_string)
    """
    sigalgs = sigalgs or CHROME_SIGALGS[:8]

    # JA3 raw string
    ja3_parts = [
        f"{tls_version:04x}",                              # TLS version
        _cipher_suite_list(cipher_suites),                  # cipher suites
        _extension_list(extensions),                        # extensions
        _int_to_2byte_list(elliptic_curves),                 # elliptic curves
        _int_to_2byte_list(elliptic_curve_point_formats),   # ec point formats
        _build_ja3_tlssignature(sigalgs),                   # signature algorithms
    ]
    ja3_str = ",".join(ja3_parts)

    md5 = hashlib.md5(ja3_str.encode()).hexdigest()
    return md5, ja3_str


# ── JA4 fingerprint generation ────────────────────────────────────────────────

def _alpn_to_protocol(alpn_bytes: bytes) -> str:
    """Map ALPN bytes to 2-letter protocol code (JA4 format)."""
    if b"h2" in alpn_bytes:
        return "h2"
    elif b"http/1" in alpn_bytes:
        return "h1"
    elif b"spdy" in alpn_bytes:
        return "sp"
    return "h1"


def _cipher_code(c: int) -> str:
    """Map primary cipher to JA4 2-char cipher code."""
    # TLS 1.3 ciphers
    if c == 0x1301:
        return "c0"
    if c == 0x1302:
        return "c1"
    if c == 0x1303:
        return "c2"
    # TLS 1.2 GCM
    if c in (0xc02c, 0xc02b):
        return "c3"
    if c in (0xc030, 0xc028, 0xc027):
        return "c4"
    if c in (0xc00a, 0xc009):
        return "c5"
    # TLS 1.2 CBC
    if c in (0x009d, 0x003d, 0x002f):
        return "c6"
    return "c0"


def _version_code(v: int) -> str:
    """Map TLS version to JA4 2-char version code."""
    if v == TLS_1_3:
        return "13"
    if v == TLS_1_2:
        return "03"
    return "03"


def generate_ja4(
    cipher_suites: List[int],
    extensions: List[int],
    alpn: bytes,
    tls_version: int = TLS_1_3,
    is_tls13: bool = True,
) -> str:
    """
    Generate JA4 fingerprint string.

    JA4 format: t{version}{proto}{cipher}{extensions}{...}
    Example: t13d1516h2_9bb6e64f6d2d_c230_4a52
    """
    ver = _version_code(tls_version)
    proto = _alpn_to_protocol(alpn)
    prim_cipher = cipher_suites[0] if cipher_suites else 0x1301
    cipher = _cipher_code(prim_cipher)

    # Extension count (2 chars)
    ext_count = min(len(extensions), 99)
    ext_code = f"{ext_count:02d}"

    # Sorted first/last extension bytes (or 0 if < 2)
    if len(extensions) >= 2:
        sorted_exts = sorted(extensions)
        first = f"{sorted_exts[0]:04x}"[:2]
        last = f"{sorted_exts[-1]:04x}"[:2]
    elif len(extensions) == 1:
        first = f"{extensions[0]:04x}"[:2]
        last = "00"
    else:
        first = "00"
        last = "00"

    # Truncated sha256 of full ja3 string (for uniqueness)
    ja3_str = ",".join([
        f"{tls_version:04x}",
        _cipher_suite_list(cipher_suites),
        _extension_list(extensions),
    ])
    ja4_part = hashlib.sha256(ja3_str.encode()).hexdigest()[:12]

    return f"t{ver}{proto}{cipher}{ext_code}{first}{last}_{ja4_part}"


# ── Full TLS ClientHello construction ─────────────────────────────────────────

def build_client_hello(
    profile_name: str = "chrome_win",
    sni_host: str = "example.com",
    session_id: Optional[bytes] = None,
    psk_binder: Optional[bytes] = None,
    randomize: bool = True,
) -> bytes:
    """
    Build a realistic TLS 1.3 ClientHello bytes (suitable for JA3 generation).

    Args:
        profile_name: one of 'chrome_win', 'chrome_mac', 'firefox_win', 'safari_mac'
        sni_host: SNI hostname
        session_id: optional 32-byte session ID (random if None)
        psk_binder: optional PSK binder bytes
        randomize: if True, apply slight ordering/selection noise

    Returns:
        Raw TLS record bytes (handshake only, not length-prefixed for TLS layer)
    """
    profile = BROWSER_PROFILES.get(profile_name, BROWSER_PROFILES["chrome_win"]).copy()

    if randomize:
        # Shuffle cipher suites (keep TLS 1.3 ciphers first, max 3)
        ciphers = profile["ciphers"].copy()
        tls13_ciphers = ciphers[:3]
        remaining = ciphers[3:]
        random.shuffle(remaining)
        profile["ciphers"] = tls13_ciphers + remaining[:12]

        # Slightly shuffle extensions (keep SNI first, supported_versions second)
        exts = profile["extensions"].copy()
        priority_exts = exts[:3]
        rest = exts[3:]
        random.shuffle(rest)
        profile["extensions"] = priority_exts + rest

        # Maybe drop a group or two
        if random.random() < 0.2:
            profile["groups"] = profile["groups"][:2]

    # Build handshake structure
    handshake = bytearray()

    # Client version (for ClientHello, use TLS 1.2 even if TLS 1.3 is targeted)
    handshake += struct.pack("!H", TLS_1_2)

    # Random (32 bytes)
    if session_id is None:
        session_id = bytes(random.getrandbits(8) for _ in range(32))
    handshake += session_id  # 32 bytes

    # Cookie (empty for initial handshake)
    cookie_len = bytes([0x00])

    # Cipher suites (2-byte length + suites)
    cipher_bytes = bytearray()
    for c in profile["ciphers"]:
        cipher_bytes += struct.pack("!H", c)
    handshake += struct.pack("!H", len(cipher_bytes)) + cipher_bytes

    # Compression methods (null only = no compression)
    handshake += b"\x01\x01"

    # Extensions
    ext_data = bytearray()

    # 0x0000: server_name (SNI)
    sni_bytes = sni_host.encode("ascii")
    sni_ext = bytearray()
    sni_ext += struct.pack("!HH", len(sni_bytes) + 5, 0)          # type + len
    sni_ext += struct.pack("!H", len(sni_bytes) + 3)              # name list len
    sni_ext += bytes([0x00])                                      # name_type = host_name
    sni_ext += struct.pack("!H", len(sni_bytes))
    sni_ext += sni_bytes
    ext_data += struct.pack("!HH", 0x0000, len(sni_ext)) + sni_ext

    # 0x000a: supported_versions (TLS 1.3)
    supp_ver = bytearray()
    supp_ver += bytes([0x02])                                      # length = 2
    supp_ver += struct.pack("!H", TLS_1_3)
    ext_data += struct.pack("!HH", 0x000a, len(supp_ver)) + supp_ver

    # 0x000d: signature_algorithms
    sig_bytes = bytearray()
    sig_list = bytearray()
    for s in profile.get("sigalgs", CHROME_SIGALGS):
        sig_list += struct.pack("!H", s)
    sig_bytes += struct.pack("!H", len(sig_list))
    sig_bytes += sig_list
    ext_data += struct.pack("!HH", 0x000d, len(sig_bytes)) + sig_bytes

    # 0x0010: alpn
    alpn_ext = bytearray()
    alpn_list = profile["alpn"]
    alpn_ext += struct.pack("!H", len(alpn_list)) + alpn_list
    ext_data += struct.pack("!HH", 0x0010, len(alpn_ext)) + alpn_ext

    # 0x000b: status_request (OCSP staple)
    status_req = b"\x01\x00\x00\x00\x00"
    ext_data += struct.pack("!HH", 0x000b, len(status_req)) + status_req

    # 0x0017: status_request_v2
    status_req2 = b"\x01\x01\x00\x00\x00\x00"
    ext_data += struct.pack("!HH", 0x0017, len(status_req2)) + status_req2

    # 0x0023: session_ticket
    ext_data += struct.pack("!HH", 0x0023, 0x0000) + b""

    # 0x001b: padding (Chrome adds this to align to 512-byte boundary)
    padding_ext = bytearray()
    padding_len = 0
    ext_data += struct.pack("!HH", 0x001b, padding_len) + padding_ext

    # 0xff01: renegotiation_info
    reneg_info = b"\x00"
    ext_data += struct.pack("!HH", 0xff01, len(reneg_info)) + reneg_info

    # supported_groups (0x000a is actually the wrong ID; correct is 0x000d for groups)
    # Use 0x000a as supported_groups extension ID (legacy)
    groups_ext = bytearray()
    groups_list = bytearray()
    for g in profile.get("groups", CHROME_GROUPS):
        groups_list += struct.pack("!H", g)
    groups_ext += struct.pack("!H", len(groups_list)) + groups_list
    # Use 0x0a as extension ID (some implementations use this for supported groups)
    ext_data += struct.pack("!HH", 0x000a, len(groups_ext)) + groups_ext

    # ec_point_formats (0x000b is used; correct ID varies)
    formats_ext = bytes([0x01, 0x00])  # uncompressed
    ext_data += struct.pack("!HH", 0x000b, len(formats_ext)) + formats_ext

    # Add extension block length
    handshake += struct.pack("!H", len(ext_data)) + ext_data

    return bytes(handshake)


# ── Per-session fingerprint cache ─────────────────────────────────────────────

class TLSProfile:
    """A randomized TLS fingerprint bound to a session."""

    def __init__(self, profile_name: str = "chrome_win", sni_host: str = "example.com"):
        self.profile_name = profile_name
        self.sni_host = sni_host
        self._ciphers = None
        self._extensions = None
        self._groups = None
        self._session_id = bytes(random.getrandbits(8) for _ in range(32))
        self._randomize()

    def _randomize(self):
        profile = BROWSER_PROFILES.get(self.profile_name, BROWSER_PROFILES["chrome_win"]).copy()
        ciphers = profile["ciphers"].copy()
        random.shuffle(ciphers)
        # Keep TLS 1.3 ciphers at front
        tls13 = [c for c in ciphers if c >= 0x1301 and c <= 0x1303]
        others = [c for c in ciphers if c not in tls13]
        random.shuffle(tls13)
        self._ciphers = tls13[:3] + others[:12]

        exts = profile["extensions"].copy()
        priority = exts[:2]
        rest = exts[2:]
        random.shuffle(rest)
        self._extensions = priority + rest

        groups = profile.get("groups", CHROME_GROUPS).copy()
        if len(groups) > 2 and random.random() < 0.2:
            groups = groups[:2]
        self._groups = groups

    @property
    def ja3(self) -> Tuple[str, str]:
        return generate_ja3(
            cipher_suites=self._ciphers,
            extensions=self._extensions,
            extension_map={},
            elliptic_curves=self._groups,
            elliptic_curve_point_formats=[0],  # uncompressed
            sigalgs=CHROME_SIGALGS[:8],
        )

    @property
    def ja4(self) -> str:
        return generate_ja4(
            cipher_suites=self._ciphers,
            extensions=self._extensions,
            alpn=BROWSER_PROFILES.get(self.profile_name, {}).get("alpn", ALPN_H2),
            tls_version=TLS_1_3,
        )

    def client_hello_bytes(self) -> bytes:
        return build_client_hello(
            profile_name=self.profile_name,
            sni_host=self.sni_host,
            session_id=self._session_id,
            randomize=False,
        )


def create_tls_profile(browser_type: str = "chrome_win", sni_host: str = "example.com") -> TLSProfile:
    """Factory: create a randomized TLSProfile matching browser_type."""
    return TLSProfile(profile_name=browser_type, sni_host=sni_host)
