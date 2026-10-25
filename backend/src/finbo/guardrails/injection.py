"""Prompt-injection screening for user questions and for third-party web content.

Two layers:
1. Heuristic patterns that catch the common attack shapes (instruction overrides,
   role/system impersonation, exfiltration requests, hidden-text tricks).
2. Spotlighting: untrusted text handed to an agent is wrapped in clearly delimited
   markers with an instruction that it is data, never instructions.

Optionally, Llama Prompt Guard on Groq's free tier adds a model-based score when
GROQ_API_KEY is set. Heuristics alone are not a complete defence; the agents' tools are
read-only, which caps what a successful injection could do.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import httpx

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "override",
        re.compile(
            r"(?i)\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|all|earlier|system)\b[^.\n]{0,20}\b(instructions?|prompts?|rules?|directions?)"
        ),
    ),
    (
        "new_instructions",
        re.compile(r"(?i)\b(new|updated|real)\s+(instructions?|system\s+prompt)\s*[:\-]"),
    ),
    (
        "role_impersonation",
        re.compile(
            r"(?im)^\s*(system|assistant|developer)\s*:|<\s*/?\s*(system|im_start|im_end)\b"
        ),
    ),
    (
        "persona_hijack",
        re.compile(
            r"(?i)\byou\s+are\s+now\b|\bact\s+as\s+(?:an?\s+)?(?:unrestricted|jailbroken|dan)\b"
        ),
    ),
    (
        "prompt_exfiltration",
        re.compile(
            r"(?i)\b(reveal|print|show|repeat|output)\b[^.\n]{0,30}\b(system\s+prompt|your\s+instructions|hidden\s+prompt|api\s+key|secret)"
        ),
    ),
    (
        "tool_abuse",
        re.compile(
            r"(?i)\b(call|invoke|use)\s+the\s+\w+\s+tool\b[^.\n]{0,40}\b(with|and\s+send)\b"
        ),
    ),
    ("hidden_text", re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")),
]

UNTRUSTED_OPEN = "<<untrusted_content source={source}>>"
UNTRUSTED_CLOSE = "<<end_untrusted_content>>"


@dataclass
class InjectionVerdict:
    flagged: bool
    reasons: list[str] = field(default_factory=list)
    model_score: float | None = None


def scan(text: str, use_model: bool = True, http: httpx.Client | None = None) -> InjectionVerdict:
    reasons = [name for name, pattern in _PATTERNS if pattern.search(text)]
    score = _prompt_guard_score(text, http) if use_model else None
    flagged = bool(reasons) or (score is not None and score >= 0.8)
    if score is not None and score >= 0.8:
        reasons.append("model")
    return InjectionVerdict(flagged=flagged, reasons=reasons, model_score=score)


def spotlight(text: str, source: str) -> str:
    """Wrap third-party text so agents treat it as quoted data."""
    cleaned = _PATTERNS[-1][1].sub("", text)  # strip zero-width / bidi control characters
    return f"{UNTRUSTED_OPEN.format(source=source)}\n{cleaned}\n{UNTRUSTED_CLOSE}"


def _prompt_guard_score(text: str, http: httpx.Client | None) -> float | None:
    """Model-based score from Llama Prompt Guard on Groq, if configured. Never raises.

    Not yet verified against Groq's live API (no key during development): if the response
    isn't a bare probability, this returns None and the heuristics alone decide.
    """
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    model = os.getenv("GROQ_GUARD_MODEL", "meta-llama/llama-prompt-guard-2-86m")
    own = http is None
    http = http or httpx.Client(timeout=8.0)
    try:
        res = http.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": [{"role": "user", "content": text[:4000]}]},
        )
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"].strip()
        return float(content)
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None
    finally:
        if own:
            http.close()
