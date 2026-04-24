from __future__ import annotations

import os
import time

from sqlalchemy import create_engine, text


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured.")

    timeout_seconds = int(os.getenv("DB_WAIT_TIMEOUT_SECONDS", "90"))
    retry_interval_seconds = float(os.getenv("DB_WAIT_INTERVAL_SECONDS", "2"))
    deadline = time.monotonic() + timeout_seconds

    while True:
        engine = create_engine(database_url, future=True, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("auth-service database connection is ready.")
            return
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"auth-service could not connect to PostgreSQL within {timeout_seconds} seconds."
                ) from exc
            print(
                f"auth-service waiting for PostgreSQL; retrying in {retry_interval_seconds:.1f} seconds..."
            )
            time.sleep(retry_interval_seconds)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
