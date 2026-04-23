from __future__ import annotations

import os
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured.")
    return value


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        _require_env("DATABASE_URL"),
        future=True,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> bool:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
