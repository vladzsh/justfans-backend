# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Backend of the JustFans mini-CRM test task: Django 5 + DRF (REST) + Channels 4 (WebSocket), PostgreSQL, Redis. The OpenSpec repo (`vladzsh/justfans-spec`, locally `../openspec`) is normative for every endpoint path, payload field, and WS event — check `specs/*/spec.md` and the archived `design.md` before changing contracts.

## Commands

```bash
.venv/bin/python -m pytest                      # all tests (sqlite + InMemoryChannelLayer, no Docker needed)
.venv/bin/python -m pytest tests/test_ws.py -k idempot   # single file / keyword
.venv/bin/python manage.py seed                 # idempotent demo data (chatter1..4 / teamlead1, password demo1234)
FRONTEND_CONTEXT=../frontend docker compose up --build   # full stack on :8080 (frontend built from ../frontend instead of git URL)
```

Local dev runs on sqlite by default; `DATABASE_URL`/`REDIS_URL` env switch to Postgres/Redis (see `config/settings.py` for all env vars and defaults: `OVERDUE_SECONDS`, `PRESENCE_GRACE_SECONDS`, `HEARTBEAT_SECONDS`, `MESSAGES_PAGE_SIZE`, `CSRF_TRUSTED_ORIGINS`).

## Architecture

- **Apps:** `accounts` (custom `User` with `role`: chatter/teamlead), `chat` (models, REST, consumer, services, seed), `monitor` (teamlead snapshot).
- **`chat/services.py` is the single write path** for message creation (chatter send, fan simulation): `transaction.atomic` + `select_for_update` on the conversation, denormalized updates (`unread_count`, `awaiting_reply_since`, `last_message_at`), `group_send` only via `transaction.on_commit`. Never create `Message` rows outside it.
- **`chat/consumers.py`** — single `/ws/` endpoint for both roles; groups `chatter.{user_id}` and `monitor`; close code 4401 when unauthenticated; envelope `{"type", "payload"}`. WS `error` payload must carry `client_msg_id` when it relates to a `message.send`.
- **Idempotency:** unique `(conversation_id, client_msg_id)`; repeated `message.send` re-broadcasts the existing message instead of inserting.
- **Resync contract:** `Message.id` is the cursor — `before_id` (history pagination, DESC) and `GET /api/sync/?after_id=` (ASC, cap 500, plus conversation snapshots). Overdue/offline are *not* computed server-side; the API returns timestamps and the SPA does the math.
- **Presence:** Redis `SETEX` with TTL = grace, refreshed by WS `ping`; connect/disconnect push `monitor.update`.

## Testing notes

Tests live in `tests/` (pytest-django + pytest-asyncio). WS flows use Channels `WebsocketCommunicator`; on_commit broadcasts are asserted with `captureOnCommitCallbacks`/monkeypatch. Keep tests runnable without Docker.

## Conventions

Conventional Commits in English, one logical change per commit, never mention AI in commits, no `Co-Authored-By`, no `--amend` (history is graded by the jury). Absolute imports, no narrator comments, concise intent-only docstrings.
