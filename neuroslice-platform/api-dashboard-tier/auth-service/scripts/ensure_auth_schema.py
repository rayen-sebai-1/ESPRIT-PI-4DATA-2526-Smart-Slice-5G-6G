from __future__ import annotations

import os

from sqlalchemy import create_engine, text


AUTH_SCHEMA = "auth"


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured.")

    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{AUTH_SCHEMA}"'))
        print(f'auth-service ensured schema "{AUTH_SCHEMA}" exists.')
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
