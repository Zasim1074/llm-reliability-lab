from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


database_url = normalize_database_url(settings.database_url)
is_sqlite = database_url.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": settings.db_pool_timeout_seconds} if is_sqlite else {}
if not is_sqlite and settings.database_ssl_mode:
    connect_args["sslmode"] = settings.database_ssl_mode
engine_options = {"pool_pre_ping": True}
if not is_sqlite:
    engine_options.update({
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout_seconds,
        "pool_recycle": settings.db_pool_recycle_seconds,
    })
engine = create_engine(database_url, connect_args=connect_args, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
