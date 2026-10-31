import sqlite3

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import EvaluationRecord, Experiment, SecurityRecord


def test_health_and_cache_round_trip(api_client):
    client, _ = api_client
    assert client.get("/api/v1/health").status_code == 200
    stored = client.post("/api/v1/cache", json={"query": "API cache test", "response": "A stored answer", "namespace": "test"})
    assert stored.status_code == 200
    lookup = client.post("/api/v1/cache/lookup", json={"query": "API cache test", "namespace": "test"})
    assert lookup.json()["hit"] is True


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
    bias = client.post("/api/v1/bias-tests", json={"prompt": "Explain caching", "candidate": "Caching reduces repeat calls"})
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
        with pytest.raises(SQLAlchemyError, match="injected experiment insert failure"):
            client.post("/api/v1/security/runs", json={"name": "must roll back", "cases": cases})
    finally:
        event.remove(test_engine, "before_cursor_execute", fail_experiment_insert)

    with sessionmaker_for(test_engine)() as session:
        assert session.scalar(select(func.count(SecurityRecord.id))) == 0
        assert session.scalar(select(func.count(Experiment.id))) == 0

    retry = client.post("/api/v1/security/runs", json={"name": "retry", "cases": cases})
    assert retry.status_code == 200
    with sessionmaker_for(test_engine)() as session:
        assert session.scalar(select(func.count(SecurityRecord.id))) == 1
        assert session.scalar(select(func.count(Experiment.id))) == 1


def sessionmaker_for(engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, expire_on_commit=False)
