from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DB_PATH = Path(__file__).resolve().parent / "data" / "app.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)

Base = declarative_base()


@contextmanager
def get_session() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
