# Deploying Finbo for free

One Docker image serves the API and the web app. Every service below has a free tier
that needs no credit card.

| Piece | Free service | What you set |
|---|---|---|
| App (API + UI) | Hugging Face Spaces, Docker SDK | The Space secrets below |
| Sign-in | Clerk | Publishable key, your Space URL as an authorized party |
| Database | Neon Postgres (optional) | `DATABASE_URL` |
| LLM | GitHub Models and/or Gemini | `GITHUB_TOKEN`, `GOOGLE_API_KEY` |
| Tracing | Langfuse (optional) | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| OneDrive sync | Microsoft Entra app registration (optional) | `MS_CLIENT_ID` |
| Telegram bot | Telegram @BotFather (optional) | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` |

Without `DATABASE_URL` the app uses SQLite inside the container. On a free Space that file
is lost whenever the Space restarts, so use Neon if you want data to persist.

## 1. Clerk

1. Create an application at dashboard.clerk.com and copy the publishable key (`pk_...`).
2. Under **Domains** (or allowed origins), add your Space URL, for example
   `https://<user>-finbo.hf.space`.

## 2. Neon (optional)

Create a project at neon.tech and copy the connection string. Finbo rewrites
`postgres://` and `postgresql://` URLs to use the psycopg driver, and creates its tables
on first start.

## 3. Hugging Face Space

1. Create a Space, choose **Docker** and **Blank**.
2. Push this repository to the Space (or connect it to your GitHub repo). The Space's
   `README.md` needs this header so Hugging Face knows the port:

   ```yaml
   ---
   title: Finbo
   sdk: docker
   app_port: 7860
   ---
   ```

3. In **Settings → Variables and secrets**, add:

   | Name | Kind | Value |
   |---|---|---|
   | `VITE_CLERK_PUBLISHABLE_KEY` | Variable (build time) | `pk_...` |
   | `CLERK_PUBLISHABLE_KEY` | Secret | the same `pk_...` |
   | `CLERK_AUTHORIZED_PARTIES` | Variable | `https://<user>-finbo.hf.space` |
   | `GITHUB_TOKEN` / `GOOGLE_API_KEY` | Secret | your LLM keys |
   | `DATABASE_URL` | Secret | Neon connection string (optional) |
   | `FINBO_CONTACT` | Variable | your email, for SEC EDGAR and Wikipedia |
   | `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Secret | optional |
   | `MS_CLIENT_ID` and `VITE_MS_CLIENT_ID` | Variable | optional, see below |
   | `TELEGRAM_BOT_TOKEN` | Secret | optional, see below |
   | `TELEGRAM_BOT_USERNAME` | Variable | optional, the bot's username without @ |
   | `FINBO_TELEGRAM_IN_API` | Variable | `1` to run the bot inside the same container |

   Never set `FINBO_DEV_AUTH` or `VITE_DEV_AUTH` on a deployment: they switch
   sign-in off.

## 4. OneDrive / SharePoint sync (optional)

1. In the Entra admin center (entra.microsoft.com), register an application. Registration
   is free and needs no Azure subscription.
2. Supported account types: **personal Microsoft accounts and any organisational
   directory**.
3. Add a **Single-page application** redirect URI: your app's origin (and
   `http://localhost:5173` for local development).
4. Under **API permissions**, add Microsoft Graph delegated `Files.ReadWrite`.
5. Copy the **Application (client) ID** into `MS_CLIENT_ID` and `VITE_MS_CLIENT_ID`.
6. For a SharePoint document library instead of OneDrive, set
   `MS_GRAPH_DRIVE=sites/<site-id>/drive`.

## 5. Telegram bot (optional)

1. In Telegram, message **@BotFather**, send `/newbot`, and pick a name and a username
   ending in `bot`. BotFather replies with a token.
2. Set `TELEGRAM_BOT_TOKEN` (secret) and `TELEGRAM_BOT_USERNAME` (without the @).
3. Set `FINBO_TELEGRAM_IN_API=1` so the bot runs inside the same container as the API.
   It uses long polling, so no webhook or public URL is needed. Locally you can instead
   run it as its own process with `finbo telegram`.
4. Run only one copy of the bot per token: Telegram rejects a second poller.

People can use the bot on its own (it keeps a separate Telegram workspace), or link it to
their web account from **Settings → Chat on Telegram**, which gives a one-time
`/link CODE` valid for 10 minutes. Once linked, the web app and Telegram share the same
numbers, chats and decisions.

## Running the image yourself

```bash
docker build -t finbo --build-arg VITE_CLERK_PUBLISHABLE_KEY=pk_... .
docker run -p 7860:7860 --env-file .env finbo
```

CI builds this image and smoke-tests it on every push (see `.github/workflows/ci.yml`).
