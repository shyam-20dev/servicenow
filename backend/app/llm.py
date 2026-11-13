import json

import httpx
from pydantic import BaseModel, Field, ValidationError

from . import config
from .redact import redact

CATEGORIES = ["Network", "Hardware", "Software", "Access", "Email", "Other"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
GROUPS = ["Network Support", "Hardware Support", "Software Support", "Service Desk"]


class Triage(BaseModel):
    summary: str
    category: str
    priority: str
    assignment_group: str
    reasoning: str = ""
    steps: list[str] = Field(default_factory=list)

    def check(self) -> "Triage":
        if self.category not in CATEGORIES:
            self.category = "Other"
        if self.priority not in PRIORITIES:
            self.priority = "Medium"
        if self.assignment_group not in GROUPS:
            self.assignment_group = "Service Desk"
        return self


PROMPT = f"""You are an IT service desk triage assistant.
Read the ticket and answer ONLY with JSON having these keys:
summary (one sentence), category (one of {CATEGORIES}),
priority (one of {PRIORITIES}, based on impact and urgency),
assignment_group (one of {GROUPS}), reasoning (one sentence),
steps (list of 3-5 troubleshooting steps).
Your answer is only a suggestion that a human agent will review."""


async def triage(short_description: str, description: str) -> Triage:
    text = redact(f"{short_description}\n{description}")
    payload = {
        "model": config.OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": text},
        ],
    }
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(f"{config.OLLAMA_HOST}/api/chat", json=payload)
        r.raise_for_status()
    content = r.json()["message"]["content"]
    try:
        return Triage(**json.loads(content)).check()
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        raise ValueError(f"LLM returned invalid output: {e}") from e


async def ollama_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{config.OLLAMA_HOST}/api/tags")
            r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return {"up": True, "models": models, "model_ready": any(
            m.split(":")[0] == config.OLLAMA_MODEL.split(":")[0] for m in models)}
    except Exception as e:
        return {"up": False, "error": str(e)}


# ---------- Embeddings ----------
async def embed(texts: list[str]) -> list[list[float]]:
    """Embed texts with the local Ollama embedding model (redacted first)."""
    out: list[list[float]] = []
    async with httpx.AsyncClient(timeout=180) as client:
        for i in range(0, len(texts), 32):
            batch = [redact(t) for t in texts[i:i + 32]]
            r = await client.post(f"{config.OLLAMA_HOST}/api/embed",
                                  json={"model": config.OLLAMA_EMBED_MODEL, "input": batch})
            r.raise_for_status()
            out.extend(r.json()["embeddings"])
    return out


# ---------- Problem drafting ----------
class ProblemDraft(BaseModel):
    title: str
    root_cause: str
    actions: list[str] = Field(default_factory=list)


PROBLEM_PROMPT = """You are an IT problem manager. Several incidents were reported in a short time
and look related. Read the sample tickets and answer ONLY with one flat JSON object, exactly like:
{"title": "<service> <symptom>", "root_cause": "<one-sentence hypothesis based on the tickets>",
 "actions": ["<step 1>", "<step 2>", "<step 3>"]}
title = short Problem title naming the affected service. root_cause = one sentence hypothesis of the
shared cause. actions = 3-4 next steps for engineers. Do not invent facts the tickets do not suggest."""


def _unwrap(data):
    """Small models sometimes nest the answer; find the dict that has the expected keys."""
    if isinstance(data, dict) and "title" in data and "root_cause" in data:
        return data
    children = data.values() if isinstance(data, dict) else data if isinstance(data, list) else []
    for child in children:
        found = _unwrap(child)
        if found is not None:
            return found
    return None


async def draft_problem(samples: list[str], attempts: int = 3) -> ProblemDraft:
    text = "\n".join(f"- {redact(s)}" for s in samples)
    payload = {
        "model": config.OLLAMA_MODEL, "stream": False, "format": "json",
        "options": {"temperature": 0.2},
        "messages": [{"role": "system", "content": PROBLEM_PROMPT},
                     {"role": "user", "content": text}],
    }
    last_error = "unknown"
    for _ in range(attempts):
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{config.OLLAMA_HOST}/api/chat", json=payload)
            r.raise_for_status()
        try:
            data = _unwrap(json.loads(r.json()["message"]["content"]))
            if data is None:
                raise ValueError("answer is missing title/root_cause")
            if isinstance(data.get("actions"), str):
                data["actions"] = [data["actions"]]
            return ProblemDraft(**{k: data[k] for k in ("title", "root_cause", "actions") if k in data})
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as e:
            last_error = str(e)
    raise ValueError(f"LLM returned invalid problem draft after {attempts} attempts: {last_error}")
