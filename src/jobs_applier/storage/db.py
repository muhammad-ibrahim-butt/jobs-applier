"""SQLAlchemy database setup."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_db_engine(database_path: Path) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{database_path.resolve()}"
    return create_engine(url, echo=False)


def _ensure_run_columns(engine: Engine) -> None:
    """SQLite create_all won't add new columns — patch existing DBs."""
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(runs)")).fetchall()
        if not rows:
            return
        existing = {row[1] for row in rows}
        if "emailed" not in existing:
            conn.execute(text("ALTER TABLE runs ADD COLUMN emailed INTEGER DEFAULT 0"))
        if "notes" not in existing:
            conn.execute(text("ALTER TABLE runs ADD COLUMN notes TEXT DEFAULT ''"))


def init_db(database_path: Path) -> sessionmaker[Session]:
    engine = create_db_engine(database_path)
    from jobs_applier.storage import models  # noqa: F401 — register models

    Base.metadata.create_all(engine)
    _ensure_run_columns(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
