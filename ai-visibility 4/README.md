# AI Visibility Tracker (AEO/GEO module)

Tracks how a brand shows up across AI answer surfaces (ChatGPT, Gemini, Google AI
Overviews) for a set of tracked queries, on a schedule, and stores the history so
you can chart visibility over time.

## How it works

1. You register a **Brand** (name + aliases) and a list of **TrackedQuery** rows
   ("best project management software", "top CRM for startups", etc.) with the
   surfaces you want each checked on.
2. A scheduler (APScheduler, cron-style) fires each query at each configured
   **Provider** on an interval.
3. Each provider wraps a real API call:
   - `ChatGPTProvider` → OpenAI Chat Completions
   - `GeminiProvider` → Google Generative AI API
   - `GoogleAIOverviewProvider` → a SERP API that surfaces Google's AI Overview
     block (Google has no public AI Overview API, so this goes through a
     third-party SERP provider — see `.env.example`)
4. The raw response text is passed to `detector.py`, which uses Claude to decide:
   mentioned (bool), approximate position/prominence, sentiment, and a short
   supporting snippet — returned as structured JSON.
5. Everything is written to a `Snapshot` row. The FastAPI app exposes trend
   endpoints for a dashboard to consume.

## Why this shape

- **Providers are pluggable.** Each one just implements `.query(text) -> str`.
  Adding Perplexity, Copilot, etc. later is a new file, not a rewrite.
- **Detection is centralized and model-based**, not regex/keyword matching —
  brand mentions in generative text are rarely a clean string match ("the
  company" vs "Acme" vs "Acme Corp"), so this needs judgment, not `in` checks.
- **Scheduling and detection are decoupled from storage**, so you can swap
  SQLite → Postgres by changing one connection string in `.env`.

## Architecture: two processes, not one

`src/web.py` serves the FastAPI app only. `src/worker.py` runs the recurring
polling schedule only, in its own process, and re-syncs against the database
every minute so queries created via the API get picked up without a restart.
They're split so a web-service restart or horizontal scale-out never
duplicates or drops scheduled polling — see `CLAUDE.md` for the reasoning.

## Local setup (SQLite, single process, fastest to iterate)

```bash
cd ai-visibility
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys, leave DATABASE_URL as sqlite
alembic upgrade head    # creates tables
uvicorn src.web:app --reload   # API on http://localhost:8000
python -m src.worker            # in a second terminal: runs scheduled polling
```

## Local setup with Docker (Postgres, matches production shape)

```bash
cp .env.example .env   # fill in your API keys; DATABASE_URL is overridden by compose
docker compose up --build
# web:    http://localhost:8000
# worker: polling in the background, logs in this same terminal
```

The first time against a fresh Postgres, run migrations inside the running
web container:

```bash
docker compose exec web alembic upgrade head
```

## Database migrations

Schema changes go through Alembic, never hand-edited:

```bash
# after changing src/models.py
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Deploying

See the deployment steps in the main conversation / project notes: get real
provider API keys, provision managed Postgres, deploy `web` and `worker` as
two separate services from this same Dockerfile (different start commands —
see `docker-compose.yml` for the exact commands each uses), set env vars on
the host, add a domain, and wire up `/health` to uptime monitoring.

## Next steps to hand to Claude Code

- Add a `/dashboard` React frontend consuming `/brands/{id}/visibility`
- Add retry/backoff + rate-limit handling per provider
- Add alerting (Slack/email) when mention rate drops beyond a threshold
- Add competitor tracking (multiple brands per query, compared side by side)
- Add auth to the API before it's exposed publicly (currently open)
