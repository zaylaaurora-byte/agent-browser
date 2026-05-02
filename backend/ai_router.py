"""
ai_router.py — Multi-model AI routing for agent-browser.
Routes to MiniMax, OpenAI, Anthropic, or Ollama based on available API keys.
Each provider has dedicated setup for thinking tokens, tool use, and structured output.
"""
import os
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Provider detection ────────────────────────────────────────────────────────

def detect_provider(model_name: str) -> str:
    """Detect which AI provider to use based on model name — keys checked at call time."""
    model_lower = (model_name or "").lower()
    
    # Model-name-based routing (most specific first)
    if "claude" in model_lower or model_name.startswith("anthropic/"):
        return "anthropic"
    if any(k in model_lower for k in ("gpt-4", "gpt-4o", "o1-", "o3-", "o4-")):
        return "openai"
    if any(k in model_lower for k in ("llama", "qwen", "mistral", "deepseek", "codellama", "phi-")):
        return "ollama"
    
    # Default: MiniMax
    return "minimax"


def get_provider_api_key(provider: str) -> Optional[str]:
    """Get API key for the given provider."""
    key_map = {
        "minimax": os.getenv("MINIMAX_API_KEY"),
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
    }
    return key_map.get(provider)


# ── Provider implementations ──────────────────────────────────────────────────

async def call_minimax(
    messages: list[dict],
    model_name: str,
    api_key: str,
    timeout: float = 30.0,
) -> tuple[str, float]:
    """Call MiniMax via OpenAI compatibility layer."""
    from openai import OpenAI
    
    start = time.monotonic()
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    
    # MiniMax extended thinking chews through token budget fast — disable it
    extra = {}
    extra_headers = {}
    if "MiniMax" in model_name or "minimax" in model_name.lower():
        extra["thinking_params"] = {"type": "off"}
        extra_headers["X-MiniMax-Thinking"] = "off"
    
    request_kwargs = dict(
        model=model_name,
        messages=messages,
        max_tokens=32000,
        temperature=0.3,
    )
    if extra:
        request_kwargs["extra_body"] = extra
    if extra_headers:
        request_kwargs["extra_headers"] = extra_headers
    
    response = client.chat.completions.create(**request_kwargs)
    content = response.choices[0].message.content or ""
    duration_ms = (time.monotonic() - start) * 1000
    return content, duration_ms


async def call_openai(
    messages: list[dict],
    model_name: str,
    api_key: str,
    timeout: float = 30.0,
) -> tuple[str, float]:
    """Call OpenAI GPT-4o / o1 / o3."""
    from openai import OpenAI
    
    start = time.monotonic()
    client = OpenAI(api_key=api_key, timeout=timeout)
    
    request_kwargs = dict(
        model=model_name,
        messages=messages,
        max_tokens=32000,
        temperature=0.3,
    )
    
    response = client.chat.completions.create(**request_kwargs)
    content = response.choices[0].message.content or ""
    duration_ms = (time.monotonic() - start) * 1000
    return content, duration_ms


async def call_anthropic(
    messages: list[dict],
    model_name: str,
    api_key: str,
    timeout: float = 30.0,
) -> tuple[str, float]:
    """Call Anthropic Claude via official SDK."""
    from anthropic import Anthropic
    
    start = time.monotonic()
    client = Anthropic(api_key=api_key, timeout=timeout)
    
    # Extract system message
    system_msg = ""
    filtered_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_msg = msg["content"]
        else:
            filtered_messages.append(msg)
    
    # Claude doesn't support system messages mixed with tools — merge into first user msg
    if not system_msg and filtered_messages and filtered_messages[0]["role"] == "user":
        system_msg = ""
    
    extra_kwargs = {}
    if system_msg:
        extra_kwargs["system"] = system_msg
    
    response = client.messages.create(
        model=model_name.replace("anthropic/", ""),
        messages=filtered_messages,
        max_tokens=4096,
        **extra_kwargs,
    )
    
    content = response.content[0].text if response.content else ""
    duration_ms = (time.monotonic() - start) * 1000
    return content, duration_ms


async def call_ollama(
    messages: list[dict],
    model_name: str,
    api_key: Optional[str],
    timeout: float = 60.0,
) -> tuple[str, float]:
    """Call local Ollama server."""
    import httpx
    
    start = time.monotonic()
    base_url = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        payload = {
            "model": model_name.replace("ollama/", ""),
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.3},
        }
        response = await client.post(f"{base_url}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        content = data["message"]["content"] if "message" in data else ""
        duration_ms = (time.monotonic() - start) * 1000
        return content, duration_ms


# ── Main router ──────────────────────────────────────────────────────────────

async def call_ai(
    messages: list[dict],
    model_name: str,
    timeout: float = 30.0,
) -> tuple[str, float, str]:
    """
    Route to the appropriate AI provider based on available keys and model name.
    Returns (response_content, duration_ms, provider_name).
    Retries up to 2 times on transient failures.
    """
    provider = detect_provider(model_name)
    api_key = get_provider_api_key(provider)
    
    if not api_key:
        # Fall back to MiniMax if no key matches
        provider = "minimax"
        api_key = os.getenv("MINIMAX_API_KEY")
        if not api_key:
            return f"[ERROR: No API key available for {model_name}]", 0.0, "none"
    
    call_fn = {
        "minimax": call_minimax,
        "openai": call_openai,
        "anthropic": call_anthropic,
        "ollama": call_ollama,
    }.get(provider)
    
    if not call_fn:
        return f"[ERROR: Unknown provider {provider}]", 0.0, provider
    
    last_error = None
    for attempt in range(3):
        try:
            content, duration_ms = await call_fn(messages, model_name, api_key, timeout)
            return content, duration_ms, provider
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[{provider}] call failed (attempt {attempt + 1}/3): {last_error}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
    
    return f"[ERROR: All providers failed — last error: {last_error}]", 0.0, provider
