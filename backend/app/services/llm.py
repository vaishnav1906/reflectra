"""Shared Mistral client and async chat helper.

Every LLM call in the backend goes through ``chat_complete`` so that:
- the client is created once, lazily (after .env has been loaded),
- calls are non-blocking (``complete_async``) and never stall the event loop,
- both mistralai SDK layouts work (1.x exports ``Mistral`` at the top level,
  newer releases only under ``mistralai.client``).
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

try:  # mistralai 1.x
    from mistralai import Mistral  # type: ignore[attr-defined]
except ImportError:  # mistralai 2.x / 3.x
    try:
        from mistralai.client import Mistral  # type: ignore[no-redef]
    except ImportError:  # SDK not installed
        Mistral = None  # type: ignore[assignment,misc]

_client = None
_client_key: Optional[str] = None


def get_client():
    """Return a shared Mistral client, or None when no SDK/API key is available."""
    global _client, _client_key

    api_key = os.getenv("MISTRAL_API_KEY")
    if Mistral is None or not api_key:
        return None

    if _client is None or _client_key != api_key:
        _client = Mistral(api_key=api_key)
        _client_key = api_key
        logger.info("✅ Mistral client initialized")
    return _client


def llm_available() -> bool:
    return get_client() is not None


async def chat_complete(
    messages: List[Dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
    model: Optional[str] = None,
) -> Optional[str]:
    """Run one chat completion. Returns the stripped text, or None when the LLM is unavailable.

    Provider errors are raised so callers can decide how to fall back.
    """
    client = get_client()
    if client is None:
        return None

    response = await client.chat.complete_async(
        model=model or DEFAULT_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = response.choices[0].message.content
    if not isinstance(content, str):
        return None
    return content.strip()
