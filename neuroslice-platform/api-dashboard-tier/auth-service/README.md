# Auth Service

`auth-service` is the PostgreSQL-backed authentication and user-administration service for the protected NeuroSlice dashboard stack.

## Responsibilities

- stores roles, users, sessions, and audit logs in schema `auth`
- hashes passwords with Argon2id
- issues JWT access tokens
- rotates refresh tokens through persisted `auth.user_sessions` records
- supports logout, revocation, soft delete, and audit logging

In the integrated platform this service stays internal. Browsers reach it through Kong at `/api/auth/*`.

## Routes

Direct internal service routes:

- `GET /health`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /users`
- `POST /users`
- `PATCH /users/{user_id}`
- `DELETE /users/{user_id}`

Browser-facing routes through Kong:

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/auth/users`
- `POST /api/auth/users`
- `PATCH /api/auth/users/{userId}`
- `DELETE /api/auth/users/{userId}`

## Roles and Management Rules

Roles seeded by migrations:

- `ADMIN`
- `NETWORK_OPERATOR`
- `NETWORK_MANAGER`
- `DATA_MLOPS_ENGINEER`

Current management rules:

- only `ADMIN` can list, create, update, or delete users
- assignable roles are the three non-admin roles only
- admin accounts cannot be demoted, deactivated, or deleted through the current service logic

## Database Tables

Schema `auth` contains:

- `roles`
- `users`
- `user_sessions`
- `audit_logs`

## Startup Sequence

The container entrypoint in `scripts/start.sh` currently does this:

1. wait for PostgreSQL
2. ensure the `auth` schema exists
3. run `alembic upgrade head`
4. optionally seed the initial admin from `INITIAL_ADMIN_*`
5. start Uvicorn

The bootstrap is designed to be idempotent for repeated container starts.

## Key Environment Variables

- `DATABASE_URL`
- `PORT`
- `JWT_SECRET_KEY`
- `JWT_ACCESS_TOKEN_EXPIRES_MINUTES`
- `JWT_REFRESH_TOKEN_EXPIRES_DAYS`
- `ARGON2_MEMORY_COST`
- `ARGON2_TIME_COST`
- `ARGON2_PARALLELISM`
- `REFRESH_COOKIE_NAME`
- `REFRESH_COOKIE_PATH`
- `REFRESH_COOKIE_SECURE`
- `REFRESH_COOKIE_SAMESITE`
- `INITIAL_ADMIN_FULL_NAME`
- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`
- `INITIAL_ADMIN_ROLE`

`INITIAL_ADMIN_ROLE` is supported by the seed script and defaults to `ADMIN` when omitted.

## Local Commands

Run migrations manually:

```bash
cd neuroslice-platform/api-dashboard-tier/auth-service
alembic upgrade head
```

Seed or update the initial admin manually:

```bash
INITIAL_ADMIN_FULL_NAME="Admin NeuroSlice" \
INITIAL_ADMIN_EMAIL="admin@neuroslice.tn" \
INITIAL_ADMIN_PASSWORD="change-me-now" \
python scripts/seed_admin.py
```

Import legacy users:

```bash
python scripts/migrate_legacy_users.py --source /path/to/legacy-users.json
```
