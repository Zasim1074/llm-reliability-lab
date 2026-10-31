# Learning guide: this repository from beginner to intermediate

Work through the topics in order. Keep the app in demo mode and use disposable local data while learning. The links point to the actual implementation in this repository.

## 1. Repository walkthrough

Start with [README.md](../README.md), then inspect `apps/web/src/app/page.tsx`, `apps/api/app/main.py`, `apps/api/app/services.py`, and `apps/api/app/models.py`. The frontend is a single dashboard route; the backend is a FastAPI modular monolith; services hold use cases; SQLAlchemy models persist results.

## 2. Frontend request lifecycle

Read `apps/web/src/app/page.tsx`, beginning at the `API` constant and `api()` helper. Follow `Home` initial `useEffect` to `/experiments/summary`, the `act()` wrapper for mutation feedback, and `openExperiment()` plus the detail-loading effect for history. The helper attaches a token from `sessionStorage` and deduplicates in-flight GETs. `apps/web/src/app/page.test.tsx` tests initial loading/empty data, reset, detail navigation, criterion-weight submission, and API error display.

## 3. Backend request lifecycle

Read `apps/api/app/main.py`: `lifespan`, middleware `request_id_middleware`, `_auth_required`, safe exception handlers, then a route such as `evaluation()` or `security_run()`. Routes validate inputs through Pydantic and call services; sessions are provided by `Depends(get_db)`.

## 4. FastAPI dependency injection

Open `apps/api/app/db.py` and find `get_db()`. It creates a request-scoped SQLAlchemy `Session`, rolls back uncaught exceptions, and closes in `finally`. In `main.py`, route parameters like `db: Session = Depends(get_db)` ask FastAPI to manage that lifecycle. Tests replace `SessionLocal` in `apps/api/tests/conftest.py` with a temporary SQLite engine.

## 5. Pydantic validation

Read `apps/api/app/schemas.py`: `CacheStoreRequest`, `EvaluationRequest`, and `SecurityRunRequest` define request limits and criteria/category validation. Read `apps/api/app/config.py` to see environment validation. Try invalid API payloads through `/docs` and observe the safe 422 error response.

## 6. SQLAlchemy and Alembic

Inspect `apps/api/app/models.py` and compare it with `apps/api/migrations/versions/0001_initial.py` and `0002_provider_aware_cache.py`. `apps/api/migrations/env.py` loads the configured database URL. For a fresh local database, run `alembic upgrade head` from `apps/api`. For existing unversioned data, do not stamp until you have backed it up and verified its schema against revision 0001. `services.create_experiment()` flushes a unified run row; endpoint transaction commit persists it with related records.

## 7. Embeddings and cosine similarity

Read `apps/api/app/providers.py`, especially `EmbeddingProvider`, `OpenAIProvider.embed()`, and provider vector validation. Then read `services.cosine()`: it divides dot product by vector magnitudes and rejects incompatible lengths and zero vectors. Stored vectors record embedding model plus dimensions so the service will not compare different vector spaces. OpenAI calls are mocked in `tests/test_providers.py`; those tests do not verify live credentials or model availability.

## 8. Semantic caching

Follow `services.cache_store()` and `services.cache_lookup()`. Lookup checks namespace/TTL/invalidation and exact normalized text first. It only embeds the query when compatible model rows exist. In demo mode no embeddings are generated, so matching is exact-only. `main.py` has cache routes and the benchmark route; the benchmark measures local lookup time but estimates the cache-disabled downstream call/cost counterfactual.

## 9. LLM-as-a-Judge

Follow `main.evaluation()` → `services.evaluate()` → `OpenAIProvider.judge_response()` → `JudgeScores`. Strict structured output is parsed and validated before persistence. Demo mode instead returns `deterministic_heuristic`. `EvaluationRequest.criteria_weights` controls the weighted overall score while keeping the five criterion scores visible. See `tests/test_api.py` for weighted score validation.

## 10. Bias testing

Read `main.bias_test()` and `services.compare_pair()`. It compares A/B, swaps order, then repeats candidate scoring. The `OpenAIProvider.compare_pair()` method validates the judge's winner/confidence output. In demo mode the comparison is lexical. Two requests per diagnostic (plus repeats) are not a statistical study; inspect the returned limitations and usage/cost estimate.

## 11. Prompt injection and RAG security

Read `services.INJECTION_PATTERNS`, `matching_injection_rules()`, and `run_security()`, then `main.security_run()`. Cases contain a supplied malicious/benign label; results count pattern matches, false positives, and false negatives. The sample cases are in `main.security_samples()`. This does not protect a live RAG system, call an LLM, or cover all attacks.

## 12. Docker networking and volumes

Read `docker-compose.yml`, `docker-compose.postgres.yml`, `apps/api/Dockerfile`, and `apps/web/Dockerfile`; operator commands are in `docker.md`. Browser calls need a host/browser API URL; containers use service DNS such as `db`. `api_data` and `postgres_data` are named volumes. The one-shot `migrate` service gates API startup. Avoid `docker compose down -v` unless you intend to remove the volumes.

## 13. Supabase PostgreSQL

Read `app/config.py`, `app/db.py`, and `docs/deployment.md`. `DATABASE_URL` is parsed by SQLAlchemy/psycopg, optional `DATABASE_SSL_MODE` sets TLS mode, and pool size/overflow should respect the Supabase connection limit. The repository has not been tested against a live Supabase instance.

## 14. AWS deployment architecture

Read `docs/deployment.md`. The planned arrangement is HTTPS frontend → HTTPS API on EC2 Docker → TLS Supabase PostgreSQL and server-side OpenAI. The existing shared token/rate limiter do not provide public multi-tenant security. No AWS resource was created as part of this work.

## 15. Testing and debugging

Backend tests live in `apps/api/tests/`; run `PYTHONPATH=. python -m pytest -q` from `apps/api`. Provider tests use `httpx.MockTransport`; API tests use FastAPI `TestClient` and temp SQLite files. Frontend tests use Vitest/Testing Library; run `npm test`, `npm run lint`, and `npm run build` from `apps/web`. There is no Playwright setup, and no end-to-end tests have been run. For logs and likely issues see [troubleshooting.md](troubleshooting.md).

## Suggested hands-on exercises

1. Run an exact cache hit, then try a paraphrase in demo mode and observe the miss.
2. Configure OpenAI embeddings in an isolated environment and compare the reported model identity; watch API-side cost controls.
3. Change one evaluation weight and compare the aggregate with unchanged per-criterion scores.
4. Open an experiment from history and inspect persisted configuration/results.
5. Add a harmless sentence containing one of the detector patterns and observe a false positive; this demonstrates why the harness is not a production defense.
6. Run tests before and after a small service change; keep provider behavior mocked in unit tests.
