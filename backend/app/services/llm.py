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
import contextvars
import json
import logging
import os
from typing import AsyncIterator, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
# Tried in order when the preferred model is overloaded (503), retired (404) or times out.
GEMINI_FALLBACK_MODELS = ("gemini-3.5-flash",)
DEFAULT_GEMINI_FAST_MODEL = "gemini-3.1-flash-lite"
DEFAULT_GEMINI_HEDGE_SECONDS = "4"
GEMINI_MODEL_TIMEOUT_SECONDS = 30.0
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


def _fast_model() -> str:
    return os.getenv("GEMINI_FAST_MODEL", DEFAULT_GEMINI_FAST_MODEL)


def _gemini_models(explicit: Optional[str]) -> List[str]:
    preferred = explicit or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    models = [preferred]
    for fallback in (*GEMINI_FALLBACK_MODELS, _fast_model()):
        if fallback not in models:
            models.append(fallback)
    return models


class _ModelBusy(Exception):
    """This model is rate-limited; another model may still answer."""


class _ModelUnavailable(Exception):
    """This model is overloaded, retired or timed out; another model may still answer."""


async def _gemini_call(model_name: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> Optional[str]:
    """One request to one model. Raises _ModelBusy / _ModelUnavailable for failures worth a fallback."""
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        # Conversational replies don't need hidden "thinking"; it would also
        # eat the max_tokens budget and slow every reply down.
        "reasoning_effort": os.getenv("GEMINI_REASONING_EFFORT", "none"),
    }
    headers = {"Authorization": f"Bearer {_gemini_key()}"}
    try:
        response = await _http().post(
            f"{GEMINI_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=GEMINI_MODEL_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        raise _ModelUnavailable(f"{model_name} timed out") from exc

    if response.status_code == 429:
        raise _ModelBusy(f"{model_name} rate-limited")
    if response.status_code in (404, 500, 502, 503, 504):
        raise _ModelUnavailable(f"{model_name} HTTP {response.status_code}")
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini error {response.status_code}: {response.text[:300]}")

    data = response.json()
    choices = data.get("choices") or []
    content = (choices[0].get("message") or {}).get("content") if choices else None
    return content.strip() if isinstance(content, str) and content.strip() else None


async def _gemini_complete(
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
    model: Optional[str],
    fast: bool = False,
) -> Optional[str]:
    """Answer from the preferred model, hedged by the fast model.

    Free-tier latency swings from ~1s to 20s+. If the preferred model has not
    answered after GEMINI_HEDGE_SECONDS, the fast model is started alongside it
    and whichever answers first wins. Rate-limited or unavailable models fall
    through to the next one. `fast=True` (background work such as trait
    extraction and titles) goes straight to the fast model, which also keeps
    the preferred model's quota for replies.
    """
    models = _gemini_models(_fast_model() if fast and not model else model)
    hedge_after = float(os.getenv("GEMINI_HEDGE_SECONDS", DEFAULT_GEMINI_HEDGE_SECONDS))
    fast_model = _fast_model()
    busy = 0
    last_error = "no model tried"

    pending: Dict[asyncio.Task, str] = {}
    queue = list(models)

    def start(model_name: str) -> None:
        task = asyncio.create_task(_gemini_call(model_name, messages, max_tokens, temperature))
        pending[task] = model_name

    start(queue.pop(0))
    hedged = False
    try:
        while pending:
            timeout = None if hedged or fast_model not in queue else hedge_after
            done, _ = await asyncio.wait(pending.keys(), timeout=timeout, return_when=asyncio.FIRST_COMPLETED)

            if not done:
                # Preferred model is slow: race the fast model against it.
                queue.remove(fast_model)
                start(fast_model)
                hedged = True
                logger.info("Gemini %s slow; hedging with %s", models[0], fast_model)
                continue

            for task in done:
                pending.pop(task)
                try:
                    return task.result()
                except _ModelBusy as exc:
                    busy += 1
                    last_error = str(exc)
                except _ModelUnavailable as exc:
                    last_error = str(exc)
                logger.warning("Gemini %s; trying another model", last_error)

            if not pending and queue:
                start(queue.pop(0))
    finally:
        for task in pending:
            task.cancel()

    if busy:
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
    fast: bool = False,
) -> Optional[str]:
    """Run one chat completion. Returns stripped text, or None when no LLM is configured.

    `fast=True` marks background work (trait extraction, titles) that should use
    the quickest model. Provider errors are raised so callers can decide how to
    fall back.
    """
    provider = active_provider()
    if provider == "gemini":
        return await _gemini_complete(messages, max_tokens, temperature, model, fast=fast)
    if provider == "mistral":
        return await _mistral_complete(messages, max_tokens, temperature, model)
    return None


# ---------------------------------------------------------------------------
# Streaming: showing a reply while it is being written
# ---------------------------------------------------------------------------

STREAM_FIRST_WORD_TIMEOUT = 12.0  # the backup model gets this long to start
# While someone watches a reply being typed, waiting is felt more, so the backup
# joins sooner than for background work. Measured on the free tier: the preferred
# model starts in ~1s most of the time but sometimes takes 15s+; the backup ~1s.
DEFAULT_STREAM_HEDGE_SECONDS = "2.5"


class StreamSink:
    """Where partial replies go while a streaming request is open.

    `partial(text)` replaces what the person sees with the reply so far (replace, not
    append, so clean-up applied to the whole text never leaves stray characters).
    `reset()` takes it back: the draft was rejected and a better one is on its way.
    """

    def __init__(self, emit: Callable[[Dict[str, object]], None]):
        self._emit = emit
        self._showing = False

    def partial(self, text: str) -> None:
        if text:
            self._showing = True
            self._emit({"type": "partial", "text": text})

    def reset(self) -> None:
        if self._showing:
            self._showing = False
            self._emit({"type": "reset"})


# Set by the streaming endpoint; everything it awaits (including tasks it starts) sees it.
stream_sink: contextvars.ContextVar[Optional[StreamSink]] = contextvars.ContextVar("stream_sink", default=None)


async def _gemini_stream(model_name: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> AsyncIterator[str]:
    """Text pieces from one model as they are generated."""
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "reasoning_effort": os.getenv("GEMINI_REASONING_EFFORT", "none"),
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {_gemini_key()}"}
    async with _http().stream(
        "POST", f"{GEMINI_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=GEMINI_MODEL_TIMEOUT_SECONDS
    ) as response:
        if response.status_code >= 400:
            await response.aread()
            raise _ModelUnavailable(f"{model_name} HTTP {response.status_code}")
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                choices = json.loads(data).get("choices") or []
            except json.JSONDecodeError:
                continue
            piece = (choices[0].get("delta") or {}).get("content") if choices else None
            if isinstance(piece, str) and piece:
                yield piece


async def _first_piece(stream: AsyncIterator[str]) -> str:
    return await stream.__anext__()


async def _race_first_words(
    messages: List[Dict[str, str]], max_tokens: int, temperature: float
) -> tuple[Optional[AsyncIterator[str]], str]:
    """Start the preferred model; if it hasn't said anything after the hedge delay,
    start the fast model too. Whichever produces words first is the one streamed;
    the other is closed. Returns (stream, first piece), or (None, "") if neither starts."""
    models = _gemini_models(None)
    hedge_after = float(os.getenv("GEMINI_STREAM_HEDGE_SECONDS", DEFAULT_STREAM_HEDGE_SECONDS))
    contenders: Dict[asyncio.Task, AsyncIterator[str]] = {}

    def start(model_name: str) -> None:
        stream = _gemini_stream(model_name, messages, max_tokens, temperature)
        contenders[asyncio.create_task(_first_piece(stream))] = stream

    start(models[0])
    backup = _fast_model() if _fast_model() != models[0] else None
    deadline = asyncio.get_running_loop().time() + STREAM_FIRST_WORD_TIMEOUT + hedge_after
    winner: Optional[AsyncIterator[str]] = None
    first = ""
    try:
        while contenders and winner is None:
            now = asyncio.get_running_loop().time()
            wait_for = hedge_after if backup else max(0.0, deadline - now)
            done, _ = await asyncio.wait(contenders.keys(), timeout=wait_for, return_when=asyncio.FIRST_COMPLETED)
            if not done:
                if backup:
                    logger.info("Gemini %s slow to start; racing %s", models[0], backup)
                    start(backup)
                    backup = None
                    continue
                break  # nobody spoke before the deadline
            for task in done:
                stream = contenders.pop(task)
                try:
                    first = task.result()
                    winner = stream
                    break
                except (StopAsyncIteration, _ModelUnavailable, httpx.HTTPError, asyncio.TimeoutError) as exc:
                    logger.info("A streaming attempt gave nothing (%s)", str(exc)[:100] or type(exc).__name__)
                    await stream.aclose()
            if winner is None and not contenders and backup:
                start(backup)  # the preferred model failed outright: go straight to the backup
                backup = None
    finally:
        for task, stream in contenders.items():
            task.cancel()
            try:
                await task
            except BaseException:
                pass
            await stream.aclose()
    return winner, first


async def chat_complete_streaming(
    messages: List[Dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
    display: Optional[Callable[[str], str]] = None,
    reject_if: Optional[Callable[[str], bool]] = None,
) -> Optional[str]:
    """`chat_complete`, but the reply is shown to the open stream while it is written.

    display(text)    what to show for the text so far (e.g. with clean-up applied).
    reject_if(text)  True as soon as the draft is clearly going to be thrown away; the
                     stream is taken back and nothing more is shown from this draft.

    With no stream open, or if streaming cannot start, this is exactly `chat_complete`
    (same fallbacks, same rate-limit errors), so callers never need two code paths.
    """
    sink = stream_sink.get()
    if sink is None or active_provider() != "gemini":
        return await chat_complete(messages, max_tokens=max_tokens, temperature=temperature)

    rejected = False

    def on_text(text: str) -> None:
        nonlocal rejected
        if rejected:
            return
        if reject_if is not None and reject_if(text):
            rejected = True
            sink.reset()
            return
        sink.partial(display(text) if display else text)

    stream, text = await _race_first_words(messages, max_tokens, temperature)
    if stream is not None:
        try:
            on_text(text)
            async for piece in stream:
                text += piece
                on_text(text)
            if text.strip():
                return text.strip()
        except Exception as exc:  # dropped mid-reply: take back what was shown and answer the plain way
            logger.warning("Streaming broke off (%s)", str(exc)[:120])
            sink.reset()
        finally:
            await stream.aclose()
    else:
        logger.info("No model started streaming in time; answering without streaming")

    return await chat_complete(messages, max_tokens=max_tokens, temperature=temperature)
