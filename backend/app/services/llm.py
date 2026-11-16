"""Shared LLM access for the whole backend.

Every chat completion goes through `chat_complete`, which picks a provider:

  LLM_PROVIDER=auto (default)  -> Gemini when GEMINI_API_KEY is set, else Mistral
  LLM_PROVIDER=gemini | mistral

Gemini is called through Google's OpenAI-compatible endpoint (plain HTTPS, no
extra SDK). Mistral uses the official SDK; both SDK layouts are supported
(1.x exports `Mistral` at the top level, newer releases only under
`mistralai.client`). Rate-limit responses (429) are retried with backoff so the
free tiers degrade gracefully instead of failing the request.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
# Tried in order when the preferred model is overloaded (503), retired (404) or times out.
GEMINI_FALLBACK_MODELS = ("gemini-3.5-flash", "gemini-3.1-flash-lite")
GEMINI_MODEL_TIMEOUT_SECONDS = 25.0
DEFAULT_MISTRAL_MODEL = "mistral-small-latest"
RATE_LIMIT_RETRIES = 2
RATE_LIMIT_BACKOFF_SECONDS = (2.0, 6.0)

try:  # mistralai 1.x
    from mistralai import Mistral  # type: ignore[attr-defined]
except ImportError:  # mistralai 2.x / 3.x
    try:
        from mistralai.client import Mistral  # type: ignore[no-redef]
    except ImportError:  # SDK not installed
        Mistral = None  # type: ignore[assignment,misc]

_mistral_client = None
_mistral_client_key: Optional[str] = None
_http_client: Optional[httpx.AsyncClient] = None


class LLMRateLimited(Exception):
    """Raised when the provider keeps rate-limiting after retries."""


GOOGLE_KEY_PREFIXES = ("AIza", "AQ.")  # classic and newer Google AI Studio key formats


def _looks_like_google_key(key: str) -> bool:
    return key.startswith(GOOGLE_KEY_PREFIXES)


def _gemini_key() -> Optional[str]:
    """GEMINI_API_KEY, or a Google AI Studio key that was pasted into
    MISTRAL_API_KEY by mistake."""
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if key:
        return key
    misplaced = (os.getenv("MISTRAL_API_KEY") or "").strip()
    return misplaced if _looks_like_google_key(misplaced) else None


def _mistral_key() -> Optional[str]:
    key = (os.getenv("MISTRAL_API_KEY") or "").strip()
    return key if key and not _looks_like_google_key(key) else None


def active_provider() -> Optional[str]:
    """Return 'gemini', 'mistral' or None when no provider is configured."""
    preference = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    has_gemini = bool(_gemini_key())
    has_mistral = bool(_mistral_key()) and Mistral is not None

    if preference == "gemini":
        return "gemini" if has_gemini else None
    if preference == "mistral":
        return "mistral" if has_mistral else None
    if has_gemini:
        return "gemini"
    if has_mistral:
        return "mistral"
    return None


def get_client():
    """Shared Mistral SDK client (used for Mistral chat and embeddings), or None."""
    global _mistral_client, _mistral_client_key

    api_key = _mistral_key()
    if Mistral is None or not api_key:
        return None
    if _mistral_client is None or _mistral_client_key != api_key:
        _mistral_client = Mistral(api_key=api_key)
        _mistral_client_key = api_key
    return _mistral_client


def llm_available() -> bool:
    return active_provider() is not None


def _http() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0))
    return _http_client


def _gemini_models(explicit: Optional[str]) -> List[str]:
    preferred = explicit or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    models = [preferred]
    for fallback in GEMINI_FALLBACK_MODELS:
        if fallback not in models:
            models.append(fallback)
    return models


async def _gemini_complete(
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
    model: Optional[str],
) -> Optional[str]:
    headers = {"Authorization": f"Bearer {_gemini_key()}"}
    last_error: Optional[str] = None
    rate_limited_models = 0
    models = _gemini_models(model)

    for model_name in models:
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            # Conversational replies don't need hidden "thinking"; it would also
            # eat the max_tokens budget and slow every reply down.
            "reasoning_effort": os.getenv("GEMINI_REASONING_EFFORT", "none"),
        }
        # Free-tier quotas are per model: after one short backoff, move on to the
        # next model instead of failing the whole request.
        for attempt in range(2):
            try:
                response = await _http().post(
                    f"{GEMINI_BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=GEMINI_MODEL_TIMEOUT_SECONDS,
                )
            except httpx.TimeoutException:
                last_error = f"{model_name} timed out"
                logger.warning("Gemini %s timed out; trying next model", model_name)
                break

            if response.status_code == 429 and attempt == 0:
                logger.warning("Gemini %s rate-limited; retrying once in %.0fs", model_name, RATE_LIMIT_BACKOFF_SECONDS[0])
                await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS[0])
                continue
            if response.status_code == 429:
                rate_limited_models += 1
                last_error = f"{model_name} rate-limited"
                logger.warning("Gemini %s still rate-limited; trying next model", model_name)
                break
            if response.status_code in (404, 500, 502, 503, 504):
                last_error = f"{model_name} HTTP {response.status_code}"
                logger.warning("Gemini %s unavailable (HTTP %s); trying next model", model_name, response.status_code)
                break
            if response.status_code >= 400:
                raise RuntimeError(f"Gemini error {response.status_code}: {response.text[:300]}")

            data = response.json()
            choices = data.get("choices") or []
            content = (choices[0].get("message") or {}).get("content") if choices else None
            return content.strip() if isinstance(content, str) and content.strip() else None

    if rate_limited_models:
        # At least one model was only busy (not broken): tell callers to back off.
        raise LLMRateLimited(f"All Gemini models busy ({last_error})")
    raise RuntimeError(f"All Gemini models unavailable ({last_error})")


async def _mistral_complete(
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
    model: Optional[str],
) -> Optional[str]:
    client = get_client()
    if client is None:
        return None

    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            response = await client.chat.complete_async(
                model=model or os.getenv("MISTRAL_MODEL", DEFAULT_MISTRAL_MODEL),
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            if "429" in str(exc) and attempt < RATE_LIMIT_RETRIES:
                await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS[min(attempt, len(RATE_LIMIT_BACKOFF_SECONDS) - 1)])
                continue
            if "429" in str(exc):
                raise LLMRateLimited("Mistral rate limit exceeded") from exc
            raise
        content = response.choices[0].message.content
        return content.strip() if isinstance(content, str) and content.strip() else None
    return None


async def chat_complete(
    messages: List[Dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
    model: Optional[str] = None,
) -> Optional[str]:
    """Run one chat completion. Returns stripped text, or None when no LLM is configured.

    Provider errors are raised so callers can decide how to fall back.
    """
    provider = active_provider()
    if provider == "gemini":
        return await _gemini_complete(messages, max_tokens, temperature, model)
    if provider == "mistral":
        return await _mistral_complete(messages, max_tokens, temperature, model)
    return None
