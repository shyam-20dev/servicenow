"""Thin client for any OpenAI-compatible API (chat completions + embeddings).

Works with OpenAI, Groq, Together, OpenRouter, Google Gemini's OpenAI-compatible
endpoint, Azure-style gateways, or a local Ollama server - just change .env.
The API key is only ever sent in the Authorization header; it is never logged
and never appears in error messages.
"""
import json
import re
from typing import Any, Dict, List

import httpx

from ..config import get_settings


class LLMError(Exception):
    """Any failure talking to the LLM/embedding provider (message is safe to show)."""


def _post(url: str, key: str, payload: dict, timeout: float) -> dict:
    try:
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except httpx.TimeoutException:
        raise LLMError("The AI provider timed out.")
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the AI provider ({type(e).__name__}).")
    if r.status_code == 401:
        raise LLMError("The AI provider rejected the API key (401). Check LLM_API_KEY.")
    if r.status_code == 429:
        raise LLMError("The AI provider rate limit / quota was reached (429).")
    if r.status_code >= 400:
        raise LLMError(f"The AI provider returned HTTP {r.status_code}.")
    try:
        return r.json()
    except ValueError:
        raise LLMError("The AI provider returned a non-JSON response.")


def chat(messages: List[Dict[str, str]], json_mode: bool = False,
         temperature: float = 0.2, max_tokens: int = 900) -> str:
    s = get_settings()
    if not s.llm_configured:
        raise LLMError("No LLM API key configured.")
    payload: Dict[str, Any] = {
        "model": s.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    url = f"{s.llm_base_url}/chat/completions"
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
        try:
            data = _post(url, s.llm_api_key, payload, s.llm_timeout)
        except LLMError as e:
            # Some providers do not support response_format; retry once without it.
            if "HTTP 400" not in str(e):
                raise
            payload.pop("response_format")
            data = _post(url, s.llm_api_key, payload, s.llm_timeout)
    else:
        data = _post(url, s.llm_api_key, payload, s.llm_timeout)
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise LLMError("The AI provider response had an unexpected shape.")


def parse_json_object(text: str) -> dict:
    """Robustly pull a JSON object out of model output (handles ```json fences / extra prose)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        obj = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("The model did not return JSON.")
        try:
            obj = json.loads(text[start:end + 1])
        except ValueError:
            raise LLMError("The model returned malformed JSON.")
    if not isinstance(obj, dict):
        raise LLMError("The model returned JSON that is not an object.")
    return obj


def chat_json(messages: List[Dict[str, str]]) -> dict:
    return parse_json_object(chat(messages, json_mode=True))


def embed(texts: List[str]) -> List[List[float]]:
    """Return one embedding vector per input text."""
    s = get_settings()
    if not s.embeddings_configured:
        raise LLMError("No embedding API key configured.")
    vectors: List[List[float]] = []
    for i in range(0, len(texts), 64):  # batch to keep requests small
        batch = texts[i:i + 64]
        data = _post(
            f"{s.embedding_base_url}/embeddings",
            s.embedding_api_key,
            {"model": s.embedding_model, "input": batch},
            s.llm_timeout,
        )
        try:
            items = sorted(data["data"], key=lambda d: d["index"])
            vectors.extend([list(map(float, d["embedding"])) for d in items])
        except (KeyError, TypeError, ValueError):
            raise LLMError("The embedding response had an unexpected shape.")
    if len(vectors) != len(texts):
        raise LLMError("Embedding count mismatch.")
    return vectors
