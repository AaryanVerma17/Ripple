"""Thin clients for the two model providers. Keys stay on the server and never appear in errors or logs."""
from __future__ import annotations

import json
import re

import httpx

from .config import settings

_transport: httpx.AsyncBaseTransport | None = None  # tests inject a mock transport here


class LLMError(Exception):
    """A provider call failed. The message is safe to show to the user."""


def _client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, transport=_transport)


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a model reply, tolerating code fences and chatter."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE)
    for candidate in (t, t[t.find("{"): t.rfind("}") + 1] if "{" in t else ""):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            continue
    return None


async def nebius_chat(messages: list[dict], max_tokens: int = 900, model: str | None = None) -> str:
    if not settings.text_ai_configured:
        raise LLMError("The text model is not configured.")
    url = settings.nebius_base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    payload = {"model": model or settings.nebius_model, "temperature": 0.1, "max_tokens": max_tokens, "messages": messages}
    if settings.nebius_json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {settings.nebius_api_key}", "Content-Type": "application/json"}
    try:
        async with _client(settings.nebius_timeout_seconds) as c:
            r = await c.post(url, headers=headers, json=payload)
            if r.status_code == 400 and "response_format" in payload:  # model doesn't support JSON mode
                payload.pop("response_format")
                r = await c.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
    except httpx.HTTPStatusError as e:
        raise LLMError(f"The text model returned HTTP {e.response.status_code}. Check NEBIUS_MODEL and NEBIUS_BASE_URL.")
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as e:
        raise LLMError(f"The text model could not be reached or replied unexpectedly ({type(e).__name__}).")


async def gemini_generate(parts: list[dict], max_tokens: int = 1200) -> str:
    """parts: [{"text": ...}, {"inline_data": {"mime_type": ..., "data": <base64>}}]"""
    if not settings.gemini_api_key:
        raise LLMError("Gemini is not configured.")
    url = f"{settings.gemini_base_url.rstrip('/')}/models/{settings.gemini_model}:generateContent"
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json", "maxOutputTokens": max_tokens}}
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    try:
        async with _client(60) as c:
            r = await c.post(url, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        hint = " Check GEMINI_MODEL." if code in (400, 404) else " Check GEMINI_API_KEY." if code in (401, 403) else ""
        raise LLMError(f"Gemini returned HTTP {code}.{hint}")
    except (httpx.HTTPError, ValueError) as e:
        raise LLMError(f"Gemini could not be reached ({type(e).__name__}).")
    if data.get("promptFeedback", {}).get("blockReason"):
        raise LLMError("Gemini declined to read this image.")
    try:
        parts_out = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts_out)
    except (KeyError, IndexError, TypeError):
        raise LLMError("Gemini replied in an unexpected format.")


async def nebius_vision(prompt: str, image_b64: str, mime: str) -> str:
    if not settings.nebius_vision_model:
        raise LLMError("No Nebius vision model is configured.")
    messages = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}}]}]
    return await nebius_chat(messages, max_tokens=1200, model=settings.nebius_vision_model)
