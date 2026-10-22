# WHIZY AI 2.0 — Hosted Hybrid Edition

WHIZY AI 2.0 keeps the premium mobile-first interface from the previous build and adds the foundations for a **multi-user online app**: account sign-up/sign-in, per-account cloud conversation history, a server-side AI proxy, and a deployment path.

## What this build includes

- The existing responsive workspace UI: AI chat, web research, document analysis, code studio, image studio, writing studio, dark/light theme, mobile drawer, and export.
- Supabase email/password authentication.
- Cloud-synced conversation records stored per account in Supabase Postgres.
- Row-level security (RLS) policies so users can only access their own conversation rows.
- A Python backend that validates the user's Supabase access token before AI, search, or image requests.
- AI/search provider secrets configured as server environment variables, never in browser code.
- Basic per-account request rate limiting and request-size limits.
- Render deployment manifest (`render.yaml`) and environment-variable template (`.env.example`).

## Important: this ZIP is the source code, not an already-published public website

For multiple people to use the app, the owner must create a Supabase project, configure the public `config.js`, set server secrets in the hosting dashboard, and deploy the source. I cannot create or configure those third-party accounts on your behalf from this ZIP. The AI provider and optional web/image services may cost money or have usage limits.

## Deployment from an Android phone

You do not need Termux to host the online app. Use Chrome and the provider dashboards below. For the easiest repeatable deployment, create a GitHub repository and upload the files from this ZIP, then connect that repository to Render.

### 1. Create the database and accounts backend

1. Create a project at [Supabase](https://supabase.com/).
2. In **Project Settings → API** (or the API keys section), copy the project URL and the publishable/anon key. The browser key is intended to be public; **never use the `service_role` key in `config.js`**.
3. Open **SQL Editor** in Supabase and run the full contents of `supabase-schema.sql`.
4. Open **Authentication → URL Configuration** and add the final Render site URL to the Site URL and Redirect URLs after deployment.
5. In **Authentication → Providers → Email**, configure email confirmation according to your needs. For a real public app, keep confirmation enabled and configure email delivery.
6. Edit `config.js` and replace `YOUR_PROJECT_ID` and `YOUR_SUPABASE_ANON_KEY` with the project URL and public anon/publishable key.

### 2. Create the AI provider configuration

1. Choose an AI provider that offers an OpenAI-compatible chat endpoint. Create an API key with the provider.
2. Keep that key private. It belongs only in Render's server environment, not in `config.js`, HTML, JavaScript, GitHub, or screenshots.
3. Optional: create a Tavily key if you want the Web Research tool.
4. Image generation requires a compatible provider/model that permits image generation. Some providers need a separate image model or billing access.

### 3. Upload the source to GitHub

1. Create a new repository on [GitHub](https://github.com/).
2. Upload the files and folders from this project to the repository root. The root should contain `server.py`, `index.html`, `app.js`, `styles.css`, `cloud.js`, `config.js`, `supabase-schema.sql`, and `render.yaml`.
3. Make sure `.env` files or provider secrets are **not** uploaded. `.env.example` contains placeholders only.

### 4. Deploy on Render

1. Create an account at [Render](https://render.com/).
2. Choose **New → Blueprint** and connect your GitHub repository containing `render.yaml`, or create a Python Web Service using the same settings.
3. Set these environment variables in the Render service dashboard:
   - `SUPABASE_URL` — your Supabase project URL
   - `SUPABASE_ANON_KEY` — the same public anon/publishable key used in `config.js`
   - `AI_API_KEY` — your private AI provider key
   - `AI_BASE_URL` — e.g. `https://api.openai.com/v1`
   - `AI_MODEL` — a model available to your provider, e.g. `gpt-4.1-mini`
   - `IMAGE_MODEL` — a compatible image model if your provider supports it
   - `TAVILY_API_KEY` — optional; needed for web research
4. Deploy and wait for Render to provide the site's public URL.
5. Add that URL to Supabase Authentication's Site URL and Redirect URLs.
6. Open the public site, create an account, and test sign-in, chat, and conversation persistence.

Render's free web services may spin down after inactivity, so the first visit after a quiet period can take a little while. Free hosting is suitable for a prototype; review current limits and costs before launching publicly.

## Local testing (optional)

With Python 3 installed, set the environment variables from `.env.example` (using real values) and run `python server.py`. Then open `http://127.0.0.1:8787`. The hosted version still requires valid Supabase configuration and a signed-in account.

## Security notes before sharing publicly

- `config.js` contains only the Supabase public key. Never place AI keys or a Supabase `service_role` key in frontend files.
- The backend validates each Supabase access token and does not accept a user-supplied provider URL or provider secret.
- The included rate limit is an in-memory prototype limit, not a full abuse-prevention or billing system. Before a broad public launch, add persistent quotas, spend caps, monitoring, logging controls, abuse reporting, and stronger operational controls.
- Configure AI provider spending limits. A public AI app can incur costs as users send prompts or request images.
- Supabase RLS protects conversation rows by user ID. Keep the provided policies enabled and never expose the database service-role key.
- Cloud history is stored in your Supabase project. Users' prompts are sent to the configured AI provider; document content is sent when the user asks WHIZY to analyze it.
- This starter does not include paid subscriptions, team workspaces, admin dashboards, password reset UX, social login, or production-grade billing/abuse prevention.

## Troubleshooting

- **“Owner setup required”**: update `config.js` and redeploy.
- **“Sign in to use WHIZY AI”**: sign in again; the access token may have expired.
- **“AI service is not configured yet”**: set `AI_API_KEY` in the hosting environment and redeploy/restart.
- **Cloud chats do not save**: verify `supabase-schema.sql` ran successfully and RLS policies exist.
- **Signup does not immediately sign in**: check the email confirmation message and confirm the account.
- **Research or image tools fail**: configure the relevant service key/model and check its access and billing.
