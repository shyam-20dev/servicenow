"""LLM provider layer: local Ollama or the Gemini API. Everything else calls chat()/embed()/status()."""
import asyncio
import re
import time

import httpx

from . import config


class LLMError(RuntimeError):
    pass


# ---------------- Ollama ----------------
async def _ollama_chat(system, user, json_mode, temperature):
    payload = {"model": config.OLLAMA_MODEL, "stream": False,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        payload["format"] = "json"
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{config.OLLAMA_HOST}/api/chat", json=payload)
        r.raise_for_status()
    return r.json()["message"]["content"]


async def _ollama_embed(texts):
    out = []
    async with httpx.AsyncClient(timeout=180) as client:
        for i in range(0, len(texts), 32):
            r = await client.post(f"{config.OLLAMA_HOST}/api/embed",
                                  json={"model": config.OLLAMA_EMBED_MODEL, "input": texts[i:i + 32]})
            r.raise_for_status()
            out.extend(r.json()["embeddings"])
    return out


async def _ollama_status():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{config.OLLAMA_HOST}/api/tags")
            r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        ready = any(m.split(":")[0] == config.OLLAMA_MODEL.split(":")[0] for m in models)
        return {"up": True, "model_ready": ready, "model": config.OLLAMA_MODEL}
    except Exception as e:
        return {"up": False, "model_ready": False, "model": config.OLLAMA_MODEL, "error": str(e)}


# ---------------- Gemini ----------------
def _gemini_headers():
    if not config.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set in .env")
    return {"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"}


def _gemini_check(r: httpx.Response):
    if r.status_code == 200:
        return
    try:
        msg = r.json()["error"]["message"]
    except Exception:
        msg = r.text[:200]
    raise LLMError(f"Gemini API error {r.status_code}: {msg}")   # key is sent as a header, never in the URL


def _retry_wait(r: httpx.Response, attempt: int) -> float:
    """Seconds to wait before retrying: Google's own hint ("retry in 11.7s") if present, else backoff."""
    m = re.search(r"retry in ([\d.]+)s", r.text)
    return min(float(m.group(1)) + 1, 65) if m else 2 * (attempt + 1)


async def _gemini_post(url: str, body: dict, timeout: float = 60) -> httpx.Response:
    """POST with retries for temporary Google errors (429 rate limit, 500/503 overload) and timeouts."""
    last, wait = None, 2
    for attempt in range(4):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(url, headers=_gemini_headers(), json=body)
        except httpx.TimeoutException:
            last, wait = LLMError("Gemini request timed out (the model may be overloaded; try a lite model)"), 2
        else:
            if r.status_code not in (429, 500, 503):
                return r
            last, wait = r, _retry_wait(r, attempt)
        if attempt < 3:
            await asyncio.sleep(wait)
    if isinstance(last, httpx.Response):
        _gemini_check(last)
    raise last


async def _gemini_chat(system, user, json_mode, temperature):
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}]}
    gen = {}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    if temperature is not None:
        gen["temperature"] = temperature
    if gen:
        body["generationConfig"] = gen
    r = await _gemini_post(f"{config.GEMINI_BASE_URL}/models/{config.GEMINI_MODEL}:generateContent", body)
    _gemini_check(r)
    data = r.json()
    try:
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError):
        reason = data.get("promptFeedback", {}).get("blockReason", "no candidates returned")
        raise LLMError(f"Gemini returned no answer ({reason})")


_TASKS = {"document": "RETRIEVAL_DOCUMENT", "query": "RETRIEVAL_QUERY", "similarity": "SEMANTIC_SIMILARITY"}


async def _gemini_embed(texts, task):
    out = []
    BATCH = 10  # smaller batches to avoid payload-size and rate-limit errors on large uploads
    for i in range(0, len(texts), BATCH):
        reqs = [{"model": f"models/{config.GEMINI_EMBED_MODEL}",
                 "content": {"parts": [{"text": t}]},
                 "taskType": _TASKS.get(task, "SEMANTIC_SIMILARITY"),
                 "outputDimensionality": config.GEMINI_EMBED_DIMS} for t in texts[i:i + BATCH]]
        r = await _gemini_post(f"{config.GEMINI_BASE_URL}/models/{config.GEMINI_EMBED_MODEL}:batchEmbedContents",
                               {"requests": reqs}, timeout=120)
        _gemini_check(r)
        out.extend(e["values"] for e in r.json()["embeddings"])
        if i + BATCH < len(texts):
            await asyncio.sleep(0.5)  # breathing room between batches to avoid rate limits
    return out


_status_cache = {"t": 0.0, "v": None}


async def _gemini_status():
    if not config.GEMINI_API_KEY:
        return {"up": False, "model_ready": False, "model": config.GEMINI_MODEL, "error": "GEMINI_API_KEY is not set"}
    if _status_cache["v"] and time.time() - _status_cache["t"] < 60:
        return _status_cache["v"]
    try:
        # A real (tiny) generation call: model metadata can look fine for a model that can no longer be used.
        await _gemini_chat("Reply with the word ok.", "ping", False, 0)
        v = {"up": True, "model_ready": True, "model": config.GEMINI_MODEL}
    except Exception as e:
        v = {"up": False, "model_ready": False, "model": config.GEMINI_MODEL, "error": str(e)}
    _status_cache.update(t=time.time(), v=v)
    return v


# ---------------- Public API ----------------
async def chat(system: str, user: str, json_mode: bool = False, temperature: float | None = None) -> str:
    if config.LLM_PROVIDER == "gemini":
        return await _gemini_chat(system, user, json_mode, temperature)
    return await _ollama_chat(system, user, json_mode, temperature)


async def embed(texts: list[str], task: str = "similarity") -> list[list[float]]:
    if config.LLM_PROVIDER == "gemini":
        return await _gemini_embed(texts, task)
    return await _ollama_embed(texts)


async def status() -> dict:
    s = await (_gemini_status() if config.LLM_PROVIDER == "gemini" else _ollama_status())
    return {"provider": config.LLM_PROVIDER, **s}
