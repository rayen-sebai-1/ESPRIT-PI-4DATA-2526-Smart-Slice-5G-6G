from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_session_factory
from repository import AuthRepository
from security import hash_password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import legacy JSON users into PostgreSQL.")
    parser.add_argument("--source", required=True, help="Path to the legacy users JSON file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = Path(args.source).expanduser().resolve()
    records = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise RuntimeError("The legacy source must contain a JSON array.")

    session_factory = get_session_factory()
    created = 0
    updated = 0

    with session_factory() as db:
        repo = AuthRepository(db)
        for record in records:
            email = str(record["email"]).strip().lower()
            role_name = str(record["role"]).strip().upper()
            full_name = str(record["full_name"]).strip()
            password = str(record["password"])
            is_active = bool(record.get("is_active", True))

            role = repo.get_role_by_name(role_name)
            if role is None:
                raise RuntimeError(f"Role {role_name} does not exist.")

            user = repo.get_user_by_email(email, include_deleted=True)
            password_hash = hash_password(password)

            if user is None:
                repo.create_user(
                    full_name=full_name,
                    email=email,
                    password_hash=password_hash,
                    role_id=role.id,
                    is_active=is_active,
                    password_changed_at=datetime.now(UTC),
                )
                created += 1
            else:
                user.full_name = full_name
                user.password_hash = password_hash
                user.role_id = role.id
                user.is_active = is_active
                user.deleted_at = None
                user.password_changed_at = datetime.now(UTC)
                updated += 1

        db.commit()

    print(f"Legacy users imported. created={created} updated={updated}")


if __name__ == "__main__":
    main()
