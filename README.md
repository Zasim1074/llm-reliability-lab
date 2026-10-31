# LLM Reliability Lab

A local-first engineering lab for measuring cache behavior, scoring LLM responses, and testing prompt-injection defenses. It runs in an explicitly labeled demo mode without provider credentials, or can use the OpenAI API for embeddings and structured LLM judging. Experiments persist in SQLite locally; PostgreSQL is supported for hosted deployments.

## Capabilities and limits

- **Semantic cache:** namespace isolation, exact lookup, TTL expiry, invalidation, provider-backed embedding similarity, and bounded lookup scans. Demo mode performs exact matching only; it does not create synthetic semantic vectors.
- **Evaluation lab:** deterministic heuristic scoring in demo mode, or structured rubric scoring through the configured LLM provider.
- **Bias diagnostics:** paired candidate order swaps and repeated scoring. Results are diagnostics, not statistical evidence.
- **RAG security:** controlled pattern-based injection harness. Retrieved text is not executed; this is not a security guarantee or a substitute for testing a real application.
- **Experiment history:** persisted metrics, configuration, and result payloads.

Estimated avoided calls and costs are estimates. Provider cost estimates are shown only when both token prices are configured. The application uses a single shared bearer token, not individual accounts, workspace isolation, or enterprise identity.

## Requirements

- Python 3.11 or newer (the API dependencies and code are targeted at Python 3.11+).
- Node.js 20 or newer and npm.
- PostgreSQL for a multi-user or hosted deployment. SQLite is intended for local demo/testing.

## Local demo

```bash
cd apps/api
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd apps/web
npm ci
npm run dev
```

Open http://localhost:3000. The API docs are at http://localhost:8000/docs. Local demo mode creates missing SQLite tables, but does not alter existing tables. Apply migrations explicitly before hosted use.

## Configuration

Copy `apps/api/.env.example` to `apps/api/.env` and `apps/web/.env.example` to `apps/web/.env.local`. The API loads `.env` from its working directory, so deployment commands should run from `apps/api` or set environment variables directly.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL. Hosted PostgreSQL URL forms are normalized to `postgresql+psycopg`. |
| `DEMO_MODE` | `true` selects deterministic local demo behavior; `false` requires an access token and at least one real provider. |
| `APP_ACCESS_TOKEN` | Shared bearer token, at least 32 characters. Keep it in the hosting secret store. Enter it in Settings in each browser tab. |
| `CORS_ORIGINS` | Comma-separated exact frontend origins. Do not use `*` for hosted deployments. |
| `LLM_PROVIDER` | `demo` or `openai`; OpenAI is used for evaluation and pairwise judging. |
| `EMBEDDING_PROVIDER` | `demo` (exact-only cache) or `openai` (semantic similarity). |
| `OPENAI_API_KEY` | Server-side secret, required for each selected OpenAI provider. Never expose it to the browser. |
| `OPENAI_CHAT_MODEL` | OpenAI model used for structured judging. |
| `OPENAI_EMBEDDING_MODEL` / `OPENAI_EMBEDDING_DIMENSIONS` | Embedding model and vector size; changing these creates a distinct vector space. |
| `CACHE_SIMILARITY_THRESHOLD` / `CACHE_SCAN_LIMIT` | Similarity cutoff and maximum candidate rows examined. |
| `RATE_LIMIT_*` | Bounded process-local request limit. Configure an edge/shared limiter for multiple workers. |
| `REQUEST_BODY_MAX_BYTES` | Maximum accepted declared request content length. Enforce actual streamed body size at the reverse proxy too. |
| `LLM_INPUT_COST_PER_MILLION` / `LLM_OUTPUT_COST_PER_MILLION` | Optional pricing assumptions for usage-based estimates. |

Set `DEMO_MODE=false`, a strong `APP_ACCESS_TOKEN`, and one or both real providers to enable production-mode API behavior. OpenAI requests are sent server-side with a timeout; prompts and credentials are not included in application request logs. Use the default HTTPS provider host unless you have explicitly reviewed and configured a compatible endpoint.

## Database migrations

For a fresh database:

```bash
cd apps/api
alembic upgrade head
```

For an existing legacy database created by the earlier `create_all` application, first stop the API and make a tested backup. Verify that the existing tables match revision `0001_initial` (especially `cache_entries`), then:

```bash
cd apps/api
alembic stamp 0001_initial
alembic upgrade head
```

Revision `0002_provider_cache` makes cache embeddings nullable and adds `embedding_model`. The API checks for those columns at startup and fails with a migration instruction if a legacy schema is detected. Do not stamp a database whose schema has not been verified. Never run this migration against the checked-in local database without backing it up first.

## Deploying

This repository contains deployment configuration guidance, not a completed cloud deployment. Use a managed PostgreSQL database with network/TLS restrictions and automated backups. Keep database/provider/access-token secrets in the platform secret manager. Run migrations as a one-off release step before starting the API; do not run migrations independently from every API worker. Start the backend from `apps/api`:

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1
```

Use a reverse proxy or platform edge to terminate HTTPS, cap actual request body size, apply shared rate limits, and restrict inbound traffic. The built-in limiter is process-local and will not enforce a shared quota across workers/instances. Until a distributed limiter and user-scoped authorization are deployed, treat this as a small trusted-team tool behind network access controls. The API bearer token is shared by all users and does not provide per-user audit attribution.

For the web app, set `NEXT_PUBLIC_API_BASE_URL` to the HTTPS API origin plus `/api/v1` before building. Set the exact web origin in API `CORS_ORIGINS`. Build and serve with Node.js 20+.

## Docker

Docker Compose setup and test instructions are in [docs/docker.md](docs/docker.md). Local SQLite startup uses `docker compose up --build`; optional PostgreSQL is enabled with `docker compose --profile postgres up --build`. The Compose setup and images have not been executed in this environment because Docker is unavailable here.

## Verification

```bash
cd apps/api
PYTHONPATH=. python -m pytest -q
cd ../web
npm test
npm run lint
npm run build
```

The test suite uses SQLite and mocked provider HTTP responses. It does not verify live OpenAI credentials, managed PostgreSQL, or a cloud deployment.

## Demo walkthrough

1. Store and look up an answer in Semantic Cache. Demo mode demonstrates exact-match behavior; configure an embedding provider for semantic matching.
2. Run a cache benchmark and distinguish measured local latency from estimated avoided calls/cost.
3. Score a candidate in Evaluation Lab. Demo results are deterministic heuristic scores.
4. Compare two candidates in Bias Testing; the output describes order swaps and repeated judging limitations.
5. Run the sample cases in RAG Security and inspect attack outcomes.
6. Use Experiment History to browse saved runs. Settings can reset local demo data.

See [docs/architecture.md](docs/architecture.md) for API boundaries and operational limitations.
