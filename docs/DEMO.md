# Demo video script (about 3 minutes)

A shot list for recording Finbo for a portfolio. Record at 1440 px wide in light mode,
then show one screen in dark mode and one on a phone. Use the sample data so no real
finances appear on screen.

Before recording: add `GITHUB_TOKEN` or `GOOGLE_API_KEY`, a Clerk key and a Telegram bot
token to `.env`, run `finbo doctor` to confirm the LLM answers, start the bot with
`finbo telegram`, and delete your workspace in Settings so the recording starts from the
welcome page.

| # | Screen | Do | Say (roughly) |
|---|---|---|---|
| 1 | Landing | Scroll from the headline to the crew | "Finbo is a crew of six AI money helpers for India and the US. Each one has one job." |
| 2 | Landing demo | Tap "When will I be debt-free?", then United States | "This is the real engine on sample numbers. No account needed." |
| 3 | Sign up | Create an account with Clerk | "Sign-in is Clerk; the API verifies its JWT on every request." |
| 4 | Welcome | Pick India, tap Meet the crew | "Finbo opens with your month at a glance." |
| 5 | Chat, Penny | Tap "Anything to sort out?", file Gym as a want | "It never guesses categories it doesn't know. You file them, and every number updates." |
| 6 | Chat, Snowy | Tap "When will I be debt-free?", then "Try ₹5,000 extra a month", then Approve | "Payoff is simulated month by month in tested Python. Nothing is a plan until I approve it." |
| 7 | Chat, Bruno | Tap "Check a stock", type RELIANCE, add it to the watchlist | "Live NSE prices with one-year return, swing and worst fall." |
| 8 | Chat, Finbo | Type "Should I clear my 42% credit card or put the money into Nifty index funds?" | "Finbo hands it to Snowy and Bruno. The reply shows who helped." |
| 9 | Chat, answer | Point at the Checks line under the answer | "Every figure is traced back to a tool result; personal details are removed before the model sees anything." |
| 10 | Chat, refusal | Type "How do I hide income from the IT department?" | "Clear requests for financial crime never reach the model." |
| 11 | Telegram | Settings → Connect Telegram, send `/link CODE` to the bot, then `/hazel` and tap a button | "Same crew, same numbers, in Telegram. Approving there lands in the same decision log." |
| 12 | Plans | Show the decisions from the web and from Telegram | "Every decision is logged with where it was made." |
| 13 | Settings | Download as Excel, approve in the Approvals sheet, import | "Excel is a third place to sign off. Only plans Finbo proposed can be approved." |
| 14 | Terminal | Run `finbo eval` | "The guardrails are scored on a labelled dataset in CI." |
| 15 | Any screen | Toggle dark mode, narrow the window to phone width | "Light and dark, desktop to phone." |
