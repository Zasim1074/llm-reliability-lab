import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import db as db_module
from app.db import Base
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'api-test.db'}")
    Base.metadata.create_all(test_engine)
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    monkeypatch.setattr(db_module, "SessionLocal", factory)
    try:
        with TestClient(app) as client:
            yield client, test_engine
    finally:
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()
