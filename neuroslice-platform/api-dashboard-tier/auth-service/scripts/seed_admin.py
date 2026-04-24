from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_session_factory
from repository import AuthRepository
from security import hash_password


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be configured.")
    return value


def main() -> None:
    email = _require_env("INITIAL_ADMIN_EMAIL").strip().lower()
    password = _require_env("INITIAL_ADMIN_PASSWORD")
    full_name = os.getenv("INITIAL_ADMIN_FULL_NAME", "NeuroSlice Administrator").strip() or "NeuroSlice Administrator"
    role_name = os.getenv("INITIAL_ADMIN_ROLE", "ADMIN").strip().upper()

    session_factory = get_session_factory()
    with session_factory() as db:
        repo = AuthRepository(db)
        role = repo.get_role_by_name(role_name)
        if role is None:
            raise RuntimeError(f"Role {role_name} does not exist. Run migrations first.")

        user = repo.get_user_by_email(email, include_deleted=True)
        password_hash = hash_password(password)

        if user is None:
            user = repo.create_user(
                full_name=full_name,
                email=email,
                password_hash=password_hash,
                role_id=role.id,
                is_active=True,
                password_changed_at=datetime.now(UTC),
            )
            action = "created"
        else:
            user.full_name = full_name
            user.password_hash = password_hash
            user.role_id = role.id
            user.is_active = True
            user.deleted_at = None
            user.password_changed_at = datetime.now(UTC)
            action = "updated"

        repo.create_audit_log(
            actor_user_id=user.id,
            target_user_id=user.id,
            action="USER_CREATE" if action == "created" else "USER_UPDATE",
            status="SUCCESS",
            ip_address=None,
            user_agent="seed_admin.py",
            metadata={"bootstrap": True, "email": email},
        )
        db.commit()

    print(f"Admin account {action}: {email}")


if __name__ == "__main__":
    main()
