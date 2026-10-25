"""One guarded run of the agent team. The API and the CLI both go through here.

policy check -> PII redaction -> injection scan -> agents (with provider fallback)
-> grounding check on the answer -> disclaimer
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from agent_framework import Message

from .agents import ToolCall, ToolCallTrace, build_team
from .guardrails import check_answer, check_request, redact, scan
from .llm import ConfiguredProvider, run_with_fallback
from .market import MarketDataProvider
from .session import FinanceSession

MAX_HISTORY = 10  # earlier turns sent with each question, to keep requests small

INJECTION_REFUSAL = (
    "That question contains wording that tries to change how Finbo behaves, so it "
    "wasn’t sent to the AI. Ask about your money in your own words and try again."
)


@dataclass
class Checks:
    refused: str | None = None  # policy category, or "injection"
    pii_redacted: dict[str, int] = field(default_factory=dict)
    input_flags: list[str] = field(default_factory=list)
    figures_checked: int = 0
    unverified_figures: list[str] = field(default_factory=list)
    risky_phrases: list[str] = field(default_factory=list)
    sources_withheld: int = 0
    disclaimer_added: bool = False

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CopilotAnswer:
    answer: str
    checks: Checks
    provider: str | None = None
    model: str | None = None
    fallbacks: list[str] = field(default_factory=list)
    trace: list[ToolCall] = field(default_factory=list)
    question_sent: str | None = None


def _withheld(trace: ToolCallTrace) -> int:
    total = 0
    for result in trace.leaf_results():
        try:
            data = json.loads(result)
        except ValueError:
            continue
        if isinstance(data, dict):
            total += int(data.get("withheld_for_safety") or 0) + int(bool(data.get("blocked")))
    return total


async def ask_copilot(
    question: str,
    session: FinanceSession,
    providers: Sequence[ConfiguredProvider],
    market_data: MarketDataProvider | None = None,
    agent: str = "finbo",
    history: Sequence[tuple[str, str]] = (),
) -> CopilotAnswer:
    """Run one guarded turn. `agent` picks the crew member (Finbo routes; others answer
    directly). `history` is earlier (role, text) turns of this chat, already redacted."""
    checks = Checks()

    decision = check_request(question)
    if not decision.allowed:
        checks.refused = decision.category
        return CopilotAnswer(answer=decision.message, checks=checks)

    redaction = redact(question)
    checks.pii_redacted = redaction.found
    verdict = scan(redaction.text)
    if verdict.flagged:
        checks.refused = "injection"
        checks.input_flags = verdict.reasons
        return CopilotAnswer(answer=INJECTION_REFUSAL, checks=checks)

    trace = ToolCallTrace()

    def build(client):
        trace.reset()
        return build_team(client, session, trace, market_data).agent(agent)

    messages = [
        Message("assistant" if role == "agent" else "user", [text])
        for role, text in history[-MAX_HISTORY:]
    ] + [Message("user", [redaction.text])]
    result = await run_with_fallback(build, messages, providers)
    answer, report = check_answer(result.response.text, trace.leaf_results(), redaction.text)
    checks.figures_checked = report.checked
    checks.unverified_figures = report.unverified
    checks.risky_phrases = report.risky_phrases
    checks.disclaimer_added = report.disclaimer_added
    checks.sources_withheld = _withheld(trace)
    return CopilotAnswer(
        answer=answer,
        checks=checks,
        provider=result.provider,
        model=result.model,
        fallbacks=result.failures,
        trace=list(trace.calls),
        question_sent=redaction.text,
    )
