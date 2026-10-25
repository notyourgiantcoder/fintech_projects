"""Command line entry point.

finbo report  [--market in|us]          deterministic report, no LLM, no keys needed
finbo ask "question" [--market in|us]   ask the personal-finance agent team
finbo doctor                            check which LLM providers are reachable
finbo serve [--port 8000]               run the HTTP API for the web UI
finbo eval [--online] [--json FILE]     score the guardrails (and, online, the agents)
finbo telegram                          run the Telegram bot (needs TELEGRAM_BOT_TOKEN)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from agent_framework import Agent

from .copilot import ask_copilot
from .core import format_amount
from .llm import (
    PROVIDERS,
    AllProvidersFailedError,
    NoProviderConfiguredError,
    configured_providers,
    load_env,
)
from .session import FinanceSession
from .tools import build_personal_tools


def _load_session(args: argparse.Namespace) -> FinanceSession:
    if args.profile or args.transactions:
        if not (args.profile and args.transactions):
            sys.exit("--profile and --transactions must be given together")
        return FinanceSession.from_files(Path(args.profile), Path(args.transactions))
    return FinanceSession.sample(args.market)


def _print_report(session: FinanceSession, extra_debt_payment: float) -> None:
    currency = session.profile.currency
    tools = build_personal_tools(session)

    def money(value: Any) -> str:
        return format_amount(Decimal(str(value)), currency)

    r = tools["analyze_spending"].func()
    print(
        f"Finbo report ({currency}, {r['period_start']} to {r['period_end']}, "
        f"{r['months']} months)\n"
    )
    print(f"  Income / month     {money(r['monthly_income']):>15}")
    print(f"  Spending / month   {money(r['avg_monthly_spending']):>15}")
    print(f"  Savings rate       {r['savings_rate_pct']:>14}%\n")

    print("  50/30/20 check")
    for b in r["buckets"]:
        target = f"(target {Decimal(b['target_pct']):.0f}%)" if b["target_pct"] else ""
        share = f"{b['pct_of_income']:>6}%"
        print(f"    {b['bucket']:<13}{money(b['monthly_avg']):>15}  {share}  {target}")
    print("\n  Top categories (monthly average)")
    for c in r["categories"][:5]:
        print(f"    {c['category']:<15}{money(c['monthly_avg']):>13}  {c['share_pct']:>6}%")
    if r["unclassified_categories"]:
        print(f"\n  Needs your review: {', '.join(r['unclassified_categories'])} (unclassified)")

    ef = tools["plan_emergency_fund"].func()
    p = ef["plan"]
    eta = f"~{p['months_to_target']} months" if p["months_to_target"] is not None else "never"
    print(
        f"\n  Emergency fund: target {p['target_months']} months = {money(p['target_amount'])}, "
        f"have {money(p['current_balance'])}, gap {money(p['gap'])}"
    )
    print(f"    {eta} at {money(p['monthly_contribution'])}/month ({'; '.join(ef['assumptions'])})")

    d = tools["compare_debt_strategies"].func(extra_monthly_payment=extra_debt_payment)
    if "comparison" not in d:
        print(f"\n  Debt: {d.get('message') or d.get('error')}")
        return
    cmp = d["comparison"]
    print(
        f"\n  Debt payoff with {money(d['monthly_budget'])}/month "
        f"(minimums {money(d['sum_of_minimums'])} + extra {money(extra_debt_payment)})"
    )
    for key in ("avalanche", "snowball"):
        plan = cmp[key]
        print(
            f"    {key:<10} {plan['months']:>3} months, interest {money(plan['total_interest'])}, "
            f"targets {plan['target_order'][0]} first"
        )
    print(
        f"    Avalanche saves {money(cmp['interest_saved_with_avalanche'])}; snowball clears "
        f"its first debt {cmp['earlier_first_win_with_snowball']} month(s) sooner"
    )


async def _ask(
    question: str, session: FinanceSession, provider: str | None, show_trace: bool
) -> int:
    try:
        providers = configured_providers(only=provider)
    except NoProviderConfiguredError as e:
        print(e, file=sys.stderr)
        return 2
    try:
        result = await ask_copilot(question, session, providers)
    except AllProvidersFailedError as e:
        print(e, file=sys.stderr)
        return 1

    print(result.answer)
    checks = result.checks
    if checks.refused:
        print(f"\n-- refused before reaching the AI: {checks.refused}", file=sys.stderr)
        return 0
    print(f"\n-- answered by {result.provider} ({result.model})", file=sys.stderr)
    for failure in result.fallbacks:
        print(f"-- fell back after: {failure}", file=sys.stderr)
    if checks.pii_redacted:
        print(f"-- redacted before sending: {checks.pii_redacted}", file=sys.stderr)
    print(
        f"-- figures checked: {checks.figures_checked}, "
        f"unverified: {checks.unverified_figures or 'none'}",
        file=sys.stderr,
    )
    if checks.risky_phrases:
        print(f"-- risky wording: {checks.risky_phrases}", file=sys.stderr)
    if show_trace:
        for call in result.trace:
            status = "ok" if call.ok else f"FAILED: {call.error}"
            args = ", ".join(f"{k}={v!r}" for k, v in call.arguments.items())
            print(f"--   {'  ' * call.depth}{call.name}({args}) {status}", file=sys.stderr)
    return 0


async def _doctor() -> int:
    healthy = 0
    for p in PROVIDERS:
        try:
            (cp,) = configured_providers(only=p.name)
        except NoProviderConfiguredError:
            print(f"  -  {p.name:<7} not configured ({p.key_env} missing in .env)")
            continue
        agent = Agent(cp.client, instructions="Reply with exactly: OK")
        try:
            response = await asyncio.wait_for(agent.run("ping"), timeout=60)
            print(f"  ok {p.name:<7} {cp.model}: {response.text.strip()[:40]!r}")
            healthy += 1
        except Exception as e:
            print(
                f"  !! {p.name:<7} {cp.model}: {type(e).__name__}: {str(e).splitlines()[0][:200]}"
            )
    return 0 if healthy else 1


def _telegram() -> int:
    import os

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print(
            "Set TELEGRAM_BOT_TOKEN in .env. Create a bot by messaging @BotFather on Telegram "
            "(free), then send /newbot.",
            file=sys.stderr,
        )
        return 2
    from .chat import ChatService
    from .store import Store
    from .telegram_bot import build_application

    store = Store()
    print("Finbo is listening on Telegram. Press Ctrl+C to stop.", file=sys.stderr)
    build_application(token, store, ChatService(store)).run_polling()
    return 0


def _eval(online: bool, provider: str | None, json_path: str | None) -> int:
    import json

    from .evals import as_json, run_offline, run_online

    results = run_offline()
    if online:
        try:
            providers = configured_providers(only=provider)
        except NoProviderConfiguredError as e:
            print(e, file=sys.stderr)
            return 2
        results.append(asyncio.run(run_online(providers)))

    for r in results:
        metrics = ", ".join(f"{k} {v}" for k, v in r.metrics.items())
        print(f"{r.name:<48} {r.passed:>3}/{r.total:<3} {metrics}")
        for failure in r.failures:
            print(f"    miss: {failure}")
    if json_path:
        Path(json_path).write_text(json.dumps(as_json(results), indent=2), encoding="utf-8")
    return 0 if all(not r.failures for r in results) else 1


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(
        prog="finbo", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    data = argparse.ArgumentParser(add_help=False)
    data.add_argument("--market", choices=["in", "us"], default="in", help="sample data set")
    data.add_argument("--profile", help="profile JSON (overrides --market)")
    data.add_argument("--transactions", help="transactions CSV (overrides --market)")

    report = sub.add_parser("report", parents=[data], help="deterministic report, no LLM")
    report.add_argument("--extra-debt-payment", type=float, default=0.0)

    ask = sub.add_parser("ask", parents=[data], help="ask the agent team")
    ask.add_argument("question")
    ask.add_argument("--provider", choices=[p.name for p in PROVIDERS])
    ask.add_argument("--no-trace", action="store_true", help="hide the tool-call trace")

    sub.add_parser("doctor", help="check LLM provider keys and connectivity")

    sub.add_parser("telegram", help="run the Telegram bot with long polling")

    evals = sub.add_parser("eval", help="score guardrails offline; --online also runs agents")
    evals.add_argument("--online", action="store_true", help="run agent scenarios on a live LLM")
    evals.add_argument("--provider", choices=[p.name for p in PROVIDERS])
    evals.add_argument("--json", help="also write results to this file")

    serve = sub.add_parser("serve", help="run the HTTP API for the web UI")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true", help="restart on code changes")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return asyncio.run(_doctor())
    if args.command == "telegram":
        return _telegram()
    if args.command == "eval":
        return _eval(args.online, args.provider, args.json)
    if args.command == "serve":
        import uvicorn

        uvicorn.run("finbo.api:app", host="127.0.0.1", port=args.port, reload=args.reload)
        return 0
    session = _load_session(args)
    if args.command == "report":
        _print_report(session, args.extra_debt_payment)
        return 0
    return asyncio.run(_ask(args.question, session, args.provider, not args.no_trace))


if __name__ == "__main__":
    raise SystemExit(main())
