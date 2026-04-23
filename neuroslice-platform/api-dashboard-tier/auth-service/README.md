# Auth Service

PostgreSQL-backed authentication and user-administration service for the protected NeuroSlice dashboard stack.

## Responsibilities

- stores users, roles, sessions, and audit logs in PostgreSQL schema `auth`
- hashes passwords with Argon2id
- issues short-lived JWT access tokens plus refresh tokens persisted in `auth.user_sessions`
- supports logout, rotation, revocation, soft delete, and audit logging

## Public Routes Through Kong

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET|POST /api/auth/users`
- `PATCH|DELETE /api/auth/users/{userId}`

## Required Environment Variables

- `DATABASE_URL`
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

## Migrations

```bash
cd neuroslice-platform/api-dashboard-tier/auth-service
alembic upgrade head
```

## Seed Initial Admin

```bash
INITIAL_ADMIN_FULL_NAME="Admin NeuroSlice" \
INITIAL_ADMIN_EMAIL="admin@neuroslice.tn" \
INITIAL_ADMIN_PASSWORD="change-me-now" \
python scripts/seed_admin.py
```

## Legacy User Import

```bash
python scripts/migrate_legacy_users.py --source /path/to/legacy-users.json
```
