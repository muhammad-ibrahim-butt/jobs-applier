"""SQLAlchemy database setup."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_db_engine(database_path: Path) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{database_path.resolve()}"
    return create_engine(url, echo=False)


def init_db(database_path: Path) -> sessionmaker[Session]:
    engine = create_db_engine(database_path)
    from jobs_applier.storage import models  # noqa: F401 — register models

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
