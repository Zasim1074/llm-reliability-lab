import sqlite3

from app.models import CacheEntry, EvaluationRecord, Experiment, SecurityRecord
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings

def test_health_and_cache_round_trip(api_client):
    client, _ = api_client
    assert client.get("/api/v1/health").status_code == 200
    stored = client.post("/api/v1/cache", json={"query": "API cache test", "response": "A stored answer", "namespace": "test"})
    assert stored.status_code == 200
    lookup = client.post("/api/v1/cache/lookup", json={"query": "API cache test", "namespace": "test"})
    assert lookup.json()["hit"] is True


def test_experiment_summary_route_is_not_captured_as_an_id(api_client):
    client, _ = api_client
    summary = client.get("/api/v1/experiments/summary")
    assert summary.status_code == 200
    assert summary.json()["total_experiments"] == 0


def test_experiment_clear_endpoint_matches_frontend_route(api_client):
    client, _ = api_client
    run = client.post("/api/v1/benchmarks", json={"query": "persist before clear"})
    assert run.status_code == 200
    cleared = client.delete("/api/v1/experiments")
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 1
    assert client.get("/api/v1/experiments/summary").json()["total_experiments"] == 0


def test_demo_data_reset_clears_all_related_tables_atomically(api_client):
    client, test_engine = api_client
    client.post("/api/v1/cache", json={"query": "remove me", "response": "answer"})
    client.post("/api/v1/evaluations", json={"prompt": "prompt", "candidate": "answer"})
    client.post("/api/v1/security/runs", json={"cases": client.get("/api/v1/security/sample-cases").json()})
    reset = client.delete("/api/v1/settings/demo-data")
    assert reset.status_code == 200
    assert reset.json()["deleted"] == {"cache_entries": 1, "evaluations": 1, "security_runs": 1, "experiments": 2}
    with sessionmaker_for(test_engine)() as session:
        assert session.scalar(select(func.count(CacheEntry.id))) == 0
        assert session.scalar(select(func.count(EvaluationRecord.id))) == 0
        assert session.scalar(select(func.count(SecurityRecord.id))) == 0
        assert session.scalar(select(func.count(Experiment.id))) == 0


def test_evaluation_and_security_are_persisted(api_client):
    client, test_engine = api_client
    evaluation = client.post("/api/v1/evaluations", json={"prompt": "Explain caching", "candidate": "Caching reduces repeat calls"})
    assert evaluation.status_code == 200
    assert evaluation.json()["judge"] == "deterministic_heuristic"
    cases = client.get("/api/v1/security/sample-cases").json()
    run = client.post("/api/v1/security/runs", json={"cases": cases})
    assert run.status_code == 200
    assert run.json()["metrics"]["blocked_attacks"] > 0
    with sessionmaker_for(test_engine)() as session:
        assert session.scalar(select(func.count(EvaluationRecord.id))) == 1
        assert session.scalar(select(func.count(SecurityRecord.id))) == 1
        assert session.scalar(select(func.count(Experiment.id))) == 2


def test_repeated_security_runs_create_exactly_one_record_pair_each(api_client):
    client, test_engine = api_client
    cases = client.get("/api/v1/security/sample-cases").json()
    responses = [client.post("/api/v1/security/runs", json={"name": "repeat", "cases": cases}) for _ in range(3)]
    assert all(response.status_code == 200 for response in responses)
    result_ids = {response.json()["id"] for response in responses}
    experiment_ids = {response.json()["experiment_id"] for response in responses}
    assert len(result_ids) == len(experiment_ids) == 3
    with sessionmaker_for(test_engine)() as session:
        assert session.scalar(select(func.count(SecurityRecord.id))) == 3
        assert session.scalar(select(func.count(Experiment.id))) == 3


def test_benchmark_and_bias_experiments_commit_after_flush(api_client):
    client, test_engine = api_client
    benchmark = client.post("/api/v1/benchmarks", json={"query": "benchmark persistence"})
    bias = client.post("/api/v1/bias-tests", json={"prompt": "Explain caching", "candidate": "Caching reduces repeat calls", "alternative_candidate": "Caching can avoid duplicate requests"})
    assert benchmark.status_code == 200
    assert bias.status_code == 200
    with sessionmaker_for(test_engine)() as session:
        assert session.scalar(select(func.count(Experiment.id)).where(Experiment.type == "benchmark")) == 1
        assert session.scalar(select(func.count(Experiment.id)).where(Experiment.type == "bias")) == 1


def test_security_result_rolls_back_when_experiment_insert_fails(api_client):
    client, test_engine = api_client
    cases = client.get("/api/v1/security/sample-cases").json()

    def fail_experiment_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO EXPERIMENTS"):
            raise IntegrityError(statement, parameters, sqlite3.IntegrityError("injected experiment insert failure"))

    event.listen(test_engine, "before_cursor_execute", fail_experiment_insert)
    try:
        failure = client.post("/api/v1/security/runs", json={"name": "must roll back", "cases": cases})
    finally:
        event.remove(test_engine, "before_cursor_execute", fail_experiment_insert)
    assert failure.status_code == 503
    assert failure.json()["error"]["code"] == "database_error"

    with sessionmaker_for(test_engine)() as session:
        assert session.scalar(select(func.count(SecurityRecord.id))) == 0
        assert session.scalar(select(func.count(Experiment.id))) == 0

    retry = client.post("/api/v1/security/runs", json={"name": "retry", "cases": cases})
    assert retry.status_code == 200
    with sessionmaker_for(test_engine)() as session:
        assert session.scalar(select(func.count(SecurityRecord.id))) == 1
        assert session.scalar(select(func.count(Experiment.id))) == 1


def test_production_access_requires_bearer_token_but_keeps_health_public(api_client, monkeypatch):
    client, _ = api_client
    monkeypatch.setattr(settings, "app_access_token", "t" * 40)
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/experiments/summary").status_code == 401
    authorized = client.get("/api/v1/experiments/summary", headers={"Authorization": "Bearer " + "t" * 40})
    assert authorized.status_code == 200


def test_rate_limiter_is_bounded_and_applies_retry_window():
    from app.main import ClientRateLimiter

    limiter = ClientRateLimiter(limit=2, window_seconds=10, client_capacity=2)
    assert limiter.allow("one", now=1) == (True, 0)
    assert limiter.allow("one", now=2) == (True, 0)
    allowed, retry_after = limiter.allow("one", now=3)
    assert allowed is False and retry_after > 0
    limiter.allow("two", now=3)
    limiter.allow("three", now=3)
    assert len(limiter.clients) == 2


def test_declared_body_size_limit_returns_request_id(api_client, monkeypatch):
    client, _ = api_client
    monkeypatch.setattr(settings, "request_body_max_bytes", 1024)
    response = client.post("/api/v1/cache", content=b"x" * 1025, headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.headers.get("X-Request-ID")
    assert response.json()["error"]["code"] == "request_too_large"


def sessionmaker_for(engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, expire_on_commit=False)
