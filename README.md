# Finbo

A friendly crew of AI money helpers for people in India and the US. Finbo merges three apps
from [awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) (AI Financial
Coach, Multi-Agent AI Researcher, AI Finance Agent Team) into one chat, on the web and in
Telegram, with human sign-off on every plan and guardrails on what the AI may say.

| | Crew member | Ask them |
|---|---|---|
| 🦊 | **Finbo** the fox, your guide | "My month at a glance", or anything; Finbo brings in the right friend |
| 🐧 | **Penny** the penguin, spending and budgets | "Where does my money go?" |
| 🐿️ | **Hazel** the squirrel, savings and safety net | "How big should my safety net be?" |
| 🦉 | **Snowy** the owl, debts and loans | "When will I be debt-free?" |
| 🐂 | **Bruno** the bull, stocks and markets | "Check RELIANCE" |
| 🦦 | **Scout** the otter, news and research | "News about Infosys" |

Each crew member is an agent that works only through tools: a tested Python calculation
engine for your own numbers, and live market and news data. Every figure in an answer is
checked against those tool results, and nothing becomes a plan until you tap Approve.

Quick questions are answered straight from the calculation engine, so the whole app works
with no AI key at all. Free typing uses the agents once a free GitHub Models or Gemini key is
added. Every service it uses has a free tier that needs no credit card.

> Educational tool, not investment advice. Personalised investment advice requires SEBI
> (India) or SEC (US) registration, which this project does not have.

## How a question flows

```
question ─► refusal policy ─► PII redaction ─► injection scan
        ─► Finbo (or the crew member you're chatting with)
              ├─► Penny / Hazel / Snowy ─► calculation engine
              ├─► Bruno ─► Yahoo Finance (NSE, BSE, US)
              └─► Scout ─► news RSS, articles, SEC EDGAR, HackerNews
                                                (third-party text scanned and fenced off)
        ─► grounding check (every ₹/$/% traced to a tool result) ─► disclaimer
        ─► answer card in web or Telegram ─► you approve or send back ─► decision log
```

## What's in it

| Area | Highlights |
|---|---|
| Calculation engine | Decimal money with lakh/crore and US formatting, CSV import with line-level errors, 50/30/20, emergency fund sizing, avalanche vs snowball simulation, exact surplus splitting |
| Agents | Microsoft Agent Framework: Finbo plus five specialists, each with its own persona and tools, agent-as-tool routing, chat history, GitHub Models with Gemini fallback, every tool call traced |
| Markets and research | Live quotes, 1-year return, volatility and drawdown, company profiles, INR/USD conversion, Google News and Economic Times RSS, article reader with SSRF protection, SEC filings, HackerNews |
| Guardrails | PII redaction (PAN, Aadhaar with Verhoeff check, IFSC, UPI, cards with Luhn check, SSN, phones, emails, accounts), prompt-injection scan on input and on fetched web text, refusal of financial-crime requests, grounding check, risky-wording check |
| Human in the loop | Approve or send back plans from a chat card on the web or in Telegram, on the Money page, or in an exported Excel workbook; OneDrive/SharePoint sync through Microsoft Graph. Buttons are looked up from the stored message, so a client can't forge an approval |
| Telegram | One bot for the whole crew: `/snowy when am I debt-free?`, tap-to-ask buttons, approve plans, send a CSV statement. Works on its own or linked to a web account with a one-time code |
| Persistence | SQLite by default, Neon Postgres via `DATABASE_URL`; workspaces, decisions and an audit log of every question with its check results |
| Web app | Bun + React + Vite, Clerk sign-in. Chat-first: crew on the left, conversation in the middle, your money on the right; Money, Markets, Plans and Settings pages; light and dark themes, phone to desktop |
| Quality | 278 backend tests, offline eval suite in CI, Langfuse tracing over OpenTelemetry, one Docker image for free hosting |

Design direction and the reason for each visual decision: [DESIGN.md](DESIGN.md).
Deployment: [docs/DEPLOY.md](docs/DEPLOY.md). Demo video script: [docs/DEMO.md](docs/DEMO.md).

## What has been verified, and how

| Part | Status |
|---|---|
| Calculation engine, API, Excel round trip, guardrails | Unit and API tests (278), offline evals |
| Yahoo Finance, Google News, Economic Times, SEC EDGAR, HackerNews, article reader | Verified live from the development machine |
| Agent routing and guardrail pipeline | Tested end to end with a scripted LLM; **not yet run against a real LLM** (needs `GITHUB_TOKEN` or `GOOGLE_API_KEY`, then `finbo eval --online`) |
| Clerk sign-in | JWT verification tested with locally signed tokens; **the browser flow needs a Clerk key** |
| OneDrive/SharePoint sync | Tested against a mocked Graph API; **needs an Entra app registration** |
| Langfuse tracing, Groq Prompt Guard, Neon | Configuration tested; **need their keys** to verify live |
| Docker image | The image's steps were reproduced locally (normal install, static serving, path traversal checks); **the image itself is built and smoke-tested in CI** because Docker wasn't available locally |
| Web app | Automated click-through (39 checks): chat quick questions, approving and filing from cards, free text without an AI key, live stock quote, Telegram link code, every page, light and dark, phone, tablet and desktop, keyboard |
| Telegram bot | Handlers tested with fake Telegram updates; **not yet run against Telegram** (needs a free token from @BotFather) |

Guardrail eval (offline, `finbo eval`): PII precision and recall 1.0 on 20 cases,
injection detection 1.0 with no false positives on 20 cases, refusal policy 13/13, grounding
9/9. These are cases written for this project, so they show the checks work as designed on
those cases, not that they would catch every real-world attack.

## Quickstart

```bash
# Backend (Python 3.11+)
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/finbo eval                                        # guardrail scores
.venv/bin/finbo report --market in --extra-debt-payment 5000  # no keys needed

# Configuration: one .env at the repo root serves backend and frontend
cp .env.example .env
#   CLERK_PUBLISHABLE_KEY and VITE_CLERK_PUBLISHABLE_KEY  (Clerk publishable key)
#   GITHUB_TOKEN and/or GOOGLE_API_KEY                    (free typing in chat)
#   FINBO_CONTACT                                         (your email, for SEC and Wikipedia)
#   TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME          (optional, from @BotFather)

# Run the web app (two terminals)
cd backend && .venv/bin/finbo serve       # API on http://127.0.0.1:8000
cd frontend && bun install && bun dev           # UI on http://localhost:5173
cd backend && .venv/bin/finbo telegram    # optional third terminal: the Telegram bot
```

No Clerk key yet? For local development only, set `FINBO_DEV_AUTH=1` and
`VITE_DEV_AUTH=1`. Sign-in is then switched off and the app shows a banner saying so.

CLI: `finbo report | ask | doctor | serve | telegram | eval [--online]`.

## Layout

```
backend/src/finbo/core/        calculation engine
backend/src/finbo/market/      quotes, history statistics, symbol resolution
backend/src/finbo/research/    news, articles, SEC filings, HackerNews
backend/src/finbo/guardrails/  PII, injection, policy, grounding
backend/src/finbo/agents/      agent team and tool-call trace
backend/src/finbo/tools/       session-bound tools the agents call
backend/src/finbo/api/         HTTP API (public, workspace, markets, Excel/OneDrive)
backend/src/finbo/evals/       labelled eval data and runner
backend/src/finbo/crew.py      the six crew members: names, colours, quick questions
backend/src/finbo/chat.py      chat service shared by web and Telegram: quick answers, cards, buttons
backend/src/finbo/telegram_bot.py  the Telegram bot
backend/src/finbo/copilot.py   one guarded agent run
backend/src/finbo/store.py     SQLite/Postgres persistence
frontend/src/                  Bun + React web app
data/samples/                  sample data for India and the US
Dockerfile, docs/              deployment and demo
```

## Credits

Built on ideas from three apps in
[awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps): AI Financial Coach
Agent, Multi-Agent AI Researcher, and AI Finance Agent Team.
