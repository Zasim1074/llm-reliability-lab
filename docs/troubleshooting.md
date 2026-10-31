# Troubleshooting

## API will not start: outdated database schema

The API fails fast if `cache_entries.embedding_model` is absent. For a fresh local DB, point `DATABASE_URL` at a new filename and run `alembic upgrade head` from `apps/api`. For existing data, stop the app, take and verify a backup, inspect that its schema matches `0001_initial`, then stamp `0001_initial` and upgrade. Never stamp or delete a database just to bypass this error. See [setup.md](setup.md#2-install-and-migrate-the-api).

## API returns 401

Check if `DEMO_MODE=false` or `APP_ACCESS_TOKEN` is set. Protected requests require `Authorization: Bearer <token>`. In the browser Settings page, enter the operator-issued token; it is kept in tab-scoped session storage. Health/readiness endpoints are public. A token change requires restarting/recreating the API and reconnecting in the browser.

## API returns a provider error

- `504 provider_timeout`: check provider reachability and `PROVIDER_TIMEOUT_SECONDS`.
- `503 provider_rate_limited`: honor `Retry-After`; reduce request frequency and check provider quota.
- `502 provider_error`: check provider service/model configuration. The API intentionally does not return the provider's raw response body.
- `422` on a custom evaluation/security request: validate criteria names, weight range, JSON structure, case category, input lengths, and 1–100 security case count.

Tests mock provider HTTP responses. Validate live key/model/billing only with a controlled provider project and a small test request.

## Cache keeps missing

In demo mode, only normalized exact text matches; semantic similarity requires `EMBEDDING_PROVIDER=openai`, stored rows generated with that same embedding model and dimensions, and a score above `CACHE_SIMILARITY_THRESHOLD`. Changing the embedding model/dimensions means earlier vectors are intentionally skipped. Check namespace, expiry, and invalidation. Cache scans are capped by `CACHE_SCAN_LIMIT`.

## CORS/browser connection errors

For local Next dev, the API origin defaults to `http://localhost:8000`. Hosted API `CORS_ORIGINS` must exactly match the frontend origin, including scheme and port. In Docker, browser API URL must be browser-accessible (`localhost` locally or public HTTPS host); `http://api:8000` is only internal Compose DNS. Rebuild the web image after changing `BROWSER_API_BASE_URL` because `NEXT_PUBLIC_*` values are compiled into its client bundle.

## PostgreSQL connection failures

- From inside Compose use hostname `db`, not `localhost`.
- For Supabase, use its connection URI, URL-encode password characters, set the provider-required `DATABASE_SSL_MODE`, and verify host/network allowlists.
- Check `DB_POOL_SIZE + DB_MAX_OVERFLOW` against the database connection quota and total app instance count.
- Run `alembic upgrade head` once before API workers. Do not run parallel migration jobs.

## Docker commands fail

Check `docker --version` and `docker compose version` (Compose 2.24+ is documented). Use `docker compose config` to inspect merged settings, then `docker compose logs migrate api web`. The Postgres profile requires `POSTGRES_PASSWORD` and a Postgres `DATABASE_URL`; its override waits for DB health. If an API image cannot write SQLite, confirm the volume target and UID 10001 ownership.

## Port is already allocated

Change `WEB_PORT`, `API_PORT`, or `DB_PORT` in the root `.env`. These are host ports; keep container ports unchanged. Browser API URL must reflect the host API port and web image must be rebuilt.

## Experiment not in history

Only benchmark, evaluation, bias, and security runs create experiment records. Cache store/lookup operations alone do not create history items. Check `/api/v1/experiments?limit=50`, then `/api/v1/experiments/{id}` for details. A failed DB transaction rolls back the operation; inspect request ID and sanitized server logs.

## Reset and persistence

The Settings reset endpoint deletes records, not database files; it is destructive and should only be used with authorized, disposable/backed-up data. `docker compose down` keeps named volumes. `docker compose down -v` deletes them. Never use it on a volume containing data you need.
