"""Evaluation runner: `finbo eval` (offline guardrails) and `--online` (live agents)."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from ..copilot import ask_copilot
from ..guardrails import check_answer, check_request, redact, scan
from ..llm import ConfiguredProvider
from ..session import FinanceSession
from .cases import AGENT_SCENARIOS, GROUNDING_CASES, INJECTION_CASES, PII_CASES, POLICY_CASES


@dataclass
class SuiteResult:
    name: str
    metrics: dict[str, float]
    failures: list[str] = field(default_factory=list)
    total: int = 0

    @property
    def passed(self) -> int:
        return self.total - len(self.failures)


def _ratio(num: int, den: int) -> float:
    return round(num / den, 3) if den else 1.0


def eval_pii() -> SuiteResult:
    tp = fp = fn = 0
    failures = []
    for text, expected in PII_CASES:
        found = set(redact(text).found)
        tp += len(found & expected)
        fp += len(found - expected)
        fn += len(expected - found)
        if found != expected:
            failures.append(f"{text!r}: expected {sorted(expected)}, got {sorted(found)}")
    return SuiteResult(
        "PII redaction",
        {"precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn)},
        failures,
        len(PII_CASES),
    )


def eval_injection() -> SuiteResult:
    tp = fp = fn = tn = 0
    failures = []
    for text, should_flag in INJECTION_CASES:
        flagged = scan(text, use_model=False).flagged
        tp += flagged and should_flag
        fp += flagged and not should_flag
        fn += (not flagged) and should_flag
        tn += (not flagged) and not should_flag
        if flagged != should_flag:
            failures.append(f"{text!r}: expected {'flag' if should_flag else 'allow'}")
    return SuiteResult(
        "Prompt-injection scan",
        {"detection_rate": _ratio(tp, tp + fn), "false_positive_rate": _ratio(fp, fp + tn)},
        failures,
        len(INJECTION_CASES),
    )


def eval_policy() -> SuiteResult:
    blocked_right = blocked_total = wrongly_blocked = allowed_total = 0
    failures = []
    for question, category in POLICY_CASES:
        decision = check_request(question)
        got = None if decision.allowed else decision.category
        if category:
            blocked_total += 1
            blocked_right += got == category
        else:
            allowed_total += 1
            wrongly_blocked += got is not None
        if got != category:
            failures.append(f"{question!r}: expected {category}, got {got}")
    return SuiteResult(
        "Refusal policy",
        {
            "block_rate": _ratio(blocked_right, blocked_total),
            "false_block_rate": _ratio(wrongly_blocked, allowed_total),
        },
        failures,
        len(POLICY_CASES),
    )


def eval_grounding() -> SuiteResult:
    caught = invented = false_alarms = honest = 0
    failures = []
    for answer, tools, question, expected in GROUNDING_CASES:
        _, report = check_answer(answer, tools, question)
        got = report.unverified
        if expected:
            invented += 1
            caught += sorted(got) == sorted(expected)
        else:
            honest += 1
            false_alarms += bool(got)
        if sorted(got) != sorted(expected):
            failures.append(f"{answer!r}: expected {expected}, got {got}")
    return SuiteResult(
        "Grounding check",
        {
            "invented_figures_caught": _ratio(caught, invented),
            "false_alarm_rate": _ratio(false_alarms, honest),
        },
        failures,
        len(GROUNDING_CASES),
    )


def run_offline() -> list[SuiteResult]:
    return [eval_pii(), eval_injection(), eval_policy(), eval_grounding()]


async def run_online(providers: list[ConfiguredProvider]) -> SuiteResult:
    failures: list[str] = []
    routed = tooled = grounded = 0
    latencies: list[float] = []
    for s in AGENT_SCENARIOS:
        session = FinanceSession.sample(s.market)  # type: ignore[arg-type]
        start = time.perf_counter()
        try:
            result = await ask_copilot(s.question, session, providers)
        except Exception as e:  # report and continue: one failure shouldn't hide the rest
            failures.append(f"{s.name}: {type(e).__name__}: {e}")
            continue
        latencies.append(time.perf_counter() - start)
        called = {c.name for c in result.trace}
        ok_route = s.expect_specialists <= called
        ok_tools = s.expect_tools <= called
        ok_ground = not result.checks.unverified_figures and not result.checks.risky_phrases
        routed += ok_route
        tooled += ok_tools
        grounded += ok_ground
        if not (ok_route and ok_tools and ok_ground):
            failures.append(
                f"{s.name}: called {sorted(called)}; unverified "
                f"{result.checks.unverified_figures}; risky {result.checks.risky_phrases}"
            )
    n = len(AGENT_SCENARIOS)
    return SuiteResult(
        f"Agent scenarios ({providers[0].provider.name}: {providers[0].model})",
        {
            "routing_accuracy": _ratio(routed, n),
            "expected_tool_use": _ratio(tooled, n),
            "fully_grounded": _ratio(grounded, n),
            "median_seconds": round(sorted(latencies)[len(latencies) // 2], 1) if latencies else 0,
        },
        failures,
        n,
    )


def as_json(results: list[SuiteResult]) -> list[dict[str, Any]]:
    return [{**asdict(r), "passed": r.passed} for r in results]
