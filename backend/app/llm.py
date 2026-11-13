import json

from pydantic import BaseModel, Field, ValidationError

from . import providers
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
    corrected: list[str] = Field(default_factory=list)  # fields replaced by safe defaults

    def check(self) -> "Triage":
        self.corrected = []
        if self.category not in CATEGORIES:
            self.category = "Other"
            self.corrected.append("category")
        if self.priority not in PRIORITIES:
            self.priority = "Medium"
            self.corrected.append("priority")
        if self.assignment_group not in GROUPS:
            self.assignment_group = "Service Desk"
            self.corrected.append("assignment_group")
        return self


PROMPT = f"""You are an IT service desk triage assistant.
Read the ticket and answer ONLY with JSON having these keys:
summary (one sentence), category (one of {CATEGORIES}),
priority (one of {PRIORITIES}, based on impact and urgency),
assignment_group (one of {GROUPS}), reasoning (one sentence),
steps (list of 3-5 troubleshooting steps).
Your answer is only a suggestion that a human agent will review."""


def _context_block(context) -> str:
    return "\n\n".join(f"[KB{a['id']}] {a['title']}\n{a['body']}" for a in context)


GROUNDING = """
Relevant knowledge base articles are provided. Base the troubleshooting steps on them
where they apply. Do not invent steps that contradict them."""


async def triage(short_description: str, description: str, context=None) -> Triage:
    text = redact(f"{short_description}\n{description}")
    if context:
        text += "\n\nKnowledge base articles:\n" + _context_block(context)
    content = await providers.chat(PROMPT + (GROUNDING if context else ""), text, json_mode=True)
    try:
        return Triage(**json.loads(content)).check()
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        raise ValueError(f"LLM returned invalid output: {e}") from e


async def llm_status() -> dict:
    return await providers.status()


# ---------- Embeddings ----------
async def embed(texts: list[str], task: str = "similarity") -> list[list[float]]:
    """Embed texts with the configured provider (personal data redacted first).
    task: "document" or "query" for retrieval, "similarity" for clustering."""
    return await providers.embed([redact(t) for t in texts], task)


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
    last_error = "unknown"
    for _ in range(attempts):
        content = await providers.chat(PROBLEM_PROMPT, text, json_mode=True, temperature=0.2)
        try:
            data = _unwrap(json.loads(content))
            if data is None:
                raise ValueError("answer is missing title/root_cause")
            if isinstance(data.get("actions"), str):
                data["actions"] = [data["actions"]]
            return ProblemDraft(**{k: data[k] for k in ("title", "root_cause", "actions") if k in data})
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as e:
            last_error = str(e)
    raise ValueError(f"LLM returned invalid problem draft after {attempts} attempts: {last_error}")


# ---------- RAG answer ----------
ASK_PROMPT = """You are an IT support assistant. Answer the question using ONLY the knowledge base
articles provided. Be concise (max 6 sentences or a short numbered list). If the articles do not
contain the answer, say you do not know. Mention the article ids you used, like [KB3]."""


async def answer(question: str, context) -> str:
    user = f"Question: {redact(question)}\n\nArticles:\n{_context_block(context)}"
    return (await providers.chat(ASK_PROMPT, user, temperature=0.2)).strip()


# ---------- Assistant (conversational RAG) ----------
REWRITE_PROMPT = """Rewrite the user's last question as one standalone search query, using the conversation
to resolve words like "it", "that" or "the second one". Return ONLY the query text, nothing else."""

CHAT_PROMPT = """You are an IT support assistant. Answer using ONLY the numbered passages from the company's
uploaded documents. Rules: be concise; cite the passage ids you used like [KB3]; if the passages do not
contain the answer, say you could not find it in the documents. Never use outside knowledge."""


def _history_text(history) -> str:
    return "\n".join(f"{m['role'].capitalize()}: {redact(m['content'])[:500]}" for m in history[-6:])


async def rewrite_query(history, question: str) -> str:
    user = f"Conversation:\n{_history_text(history)}\n\nLast question: {redact(question)}"
    out = (await providers.chat(REWRITE_PROMPT, user, temperature=0)).strip().strip('"')
    return out.splitlines()[0][:300] if out else question


async def chat_answer(question: str, history, context) -> str:
    user = (f"Conversation so far:\n{_history_text(history)}\n\n" if history else "") + \
           f"Question: {redact(question)}\n\nPassages:\n{_context_block(context)}"
    return (await providers.chat(CHAT_PROMPT, user, temperature=0.2)).strip()
