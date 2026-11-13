import re

_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b(?:\+?\d{1,3}[ -]?)?\d{10}\b"), "[PHONE]"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "[IP]"),
]


def redact(text: str) -> str:
    """Remove obvious personal data before text is sent to the LLM."""
    for pattern, token in _PATTERNS:
        text = pattern.sub(token, text)
    return text
