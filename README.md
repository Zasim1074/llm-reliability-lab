# LLM Reliability Lab

A local-first engineering lab for measuring cache behavior, scoring LLM responses, and testing prompt-injection defenses. The app runs without paid credentials and persists experiments in SQLite by default; PostgreSQL is supported through `DATABASE_URL`.

## What it demonstrates

- **Semantic cache:** namespace isolation, exact lookup, TTL expiry, invalidation, deterministic feature-hash similarity, and latency/cost benchmark reporting.
- **Evaluation lab:** criterion scores and saved runs from a clearly labeled deterministic heuristic rubric.
- **Bias diagnostics:** order swap, verbosity probe, and repeatability comparison with limitations shown in the result.
- **RAG security:** controlled pattern-based injection harness with benign and malicious samples. Retrieved text is never executed.
- **Shared experiment history:** persisted metrics, configuration, result payloads, and activity summary.

This is a reproducible demo and evaluation harness, not a security guarantee or a production quality judge. Demo similarity vectors are deterministic feature hashes, not learned semantic embeddings. Cost avoided is estimated from the configured per-call assumption in the benchmark response.

## Quick start

Requires Python 3.11+ for supported deployment and Node.js 20+.

```bash
cd apps/api
python -m venv .venv
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

Open http://localhost:3000. The API docs are at http://localhost:8000/docs. The API creates local demo tables at startup. For a deployment, apply the Alembic migration first.

## Configuration

Copy `apps/api/.env.example` to `apps/api/.env` and `apps/web/.env.example` to `apps/web/.env.local`. Key values:

| Variable | Purpose | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy URL; use `postgresql+psycopg://...` with the PostgreSQL driver installed | `sqlite:///./llm_reliability.db` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins | `http://localhost:3000` |
| `CACHE_SIMILARITY_THRESHOLD` | Similarity threshold for demo vector matching | `0.82` |
| `CACHE_TTL_SECONDS` | Default cache lifetime | `86400` |
| `DEMO_MODE` | Advertise demo mode in health response | `true` |
| `NEXT_PUBLIC_API_BASE_URL` | Browser-visible API base URL | `http://localhost:8000/api/v1` |

No secrets or provider credentials are needed. Real LLM/embedding adapters are not implemented in this deliverable; see known limitations.

## Migrations and database

```bash
cd apps/api
alembic upgrade head
```

`alembic.ini` and the migration environment read the configured database URL. SQLite is suitable for local demo use. Configure managed PostgreSQL and install a compatible PostgreSQL DBAPI driver before production use. Keep secrets in the hosting provider's environment configuration.

Existing local databases created by the app's startup `create_all` have no Alembic revision marker. Back up the database, verify its schema against the migration, then run `alembic stamp head` once to establish the existing schema's revision. Use `alembic upgrade head` for a fresh database or a database that already has Alembic history. Do not run `upgrade head` against an unversioned database that already contains these tables.

## Tests and build

```bash
cd apps/api
PYTHONPATH=. python -m pytest -q
cd ../web
npm run build
npm run lint
```

## Demo walkthrough

1. On **Semantic Cache**, store an example question and response, then run lookup to see exact-match behavior and measured lookup latency.
2. On **Cache Benchmarks**, run the local sample query set. Review measured request and latency values separately from estimated avoided calls and cost.
3. On **Evaluation Lab**, score a candidate with and without a reference; export saved runs from the module as CSV or JSON.
4. On **Bias Testing**, compare order, verbosity, and repeatability probes. These deterministic results do not imply statistical significance.
5. On **RAG Security**, run the included benign and attack cases. Compare blocked, successful, false-positive, and false-negative counts.
6. Open **Experiment History** to review saved runs, or use Settings to reset demo records.

## Deployment

### API (Render/Railway)

- Root directory: repository root; build/install from `apps/api/requirements.txt`.
- Start command: `cd apps/api && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Set `DATABASE_URL` to managed PostgreSQL, `CORS_ORIGINS` to the deployed frontend origin, and explicit cache settings.
- PostgreSQL support uses the included `psycopg[binary]` driver.
- Health check path: `/api/v1/health`.

### Frontend (Vercel)

- Set project root to `apps/web`.
- Set `NEXT_PUBLIC_API_BASE_URL` to `https://<api-host>/api/v1` before building.
- The API must allow the deployed frontend origin through `CORS_ORIGINS`.

Deployment has not been exercised against external hosting. Do not treat successful local builds as a deployment test.

## Architecture

See [docs/architecture.md](docs/architecture.md) for boundaries, request flows, and known limitations.
