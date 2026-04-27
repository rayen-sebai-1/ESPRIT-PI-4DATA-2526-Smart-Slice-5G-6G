from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, engine_from_config, pool, text

from models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be configured for Alembic.")
    return url


def _bootstrap_grants() -> None:
    """Ensure the dashboard_app role has the cross-schema privileges it needs.

    The init script creates these grants on a fresh volume, but if the volume
    already existed the script was skipped.  We re-run the idempotent grants
    here via the superuser connection so migrations always work regardless of
    volume age.

    Requires POSTGRES_SUPERUSER_URL to be set; silently skipped otherwise so
    that production environments that provision grants externally are unaffected.
    """
    superuser_url = os.getenv("POSTGRES_SUPERUSER_URL")
    if not superuser_url:
        return

    dashboard_role = os.getenv("DASHBOARD_DB_USER", "dashboard_app")
    engine = create_engine(superuser_url, poolclass=pool.NullPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS dashboard"))
        conn.execute(text(f'GRANT USAGE ON SCHEMA auth TO "{dashboard_role}"'))
        conn.execute(text(f'GRANT USAGE, CREATE ON SCHEMA dashboard TO "{dashboard_role}"'))
        conn.execute(text(f'GRANT SELECT, REFERENCES ON ALL TABLES IN SCHEMA auth TO "{dashboard_role}"'))
        conn.execute(text(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA auth TO "{dashboard_role}"'))
        conn.commit()
    engine.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="dashboard",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _bootstrap_grants()

    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = get_database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS dashboard"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="dashboard",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
