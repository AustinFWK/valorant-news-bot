# Dashboard API Design

## Problem

The bot currently exposes a single public `/stats` endpoint (server/member counts) via a raw `aiohttp` server embedded in `bot.py`. We want a dashboard on the website (patchyonline.xyz) where a Discord server admin can:

- Set which channel receives Valorant patch notes for their server
- Resend the most recent patch notes to that channel (from a stored/cached copy, not a full rescrape)
- Later: additional features requiring more of the Discord API

This spec covers the architecture and the first slice of functionality (channel config + resend). Additional admin features are future sub-projects built on this same foundation.

## Architecture Decision

**FastAPI mounted in the same process as `bot.py`, deployed on the same Ubuntu VPS.**

Considered and rejected: a fully separate API service (own repo/process). Rejected because the data these endpoints need — guild list, channel list, member counts — only exists in the live `discord.py` `Client` object's memory, and actions like "send this message to channel X" are methods on that live object. A separate service would need its own bot login or an RPC/queue bridge back to the real bot process just to act on Discord — a distributed system for a single-VPS personal project. Not worth the complexity.

Considered and rejected: keep the current raw `aiohttp` routes and just add more of them. Rejected because we're about to add real OAuth token exchange, session validation, and multiple stateful endpoints — FastAPI + Pydantic gives request/response validation and auto-generated OpenAPI docs for free, and raw aiohttp would mean hand-rolling all of that.

**Chosen approach:** A FastAPI app lives in a new `api/` package in this repo. It runs as an `asyncio` task inside `bot.py`'s event loop, started in `on_ready` alongside the existing `check_for_updates` loop (replacing the current ad-hoc aiohttp app). Same process, same port strategy, same deploy — endpoints get direct synchronous access to the live `discord.py` `client` object.

## Auth Flow (Discord OAuth2, per-admin, user-initiated)

The site remains fully browsable without logging in — patch notes, stats, and any public content stay accessible with no auth. A **"Login with Discord" button** is what kicks off OAuth; nothing happens with Discord until the user clicks it.

1. User clicks "Login with Discord" on the frontend. Frontend sends the browser to Discord's OAuth authorize URL with scopes `identify guilds`.
2. Discord redirects back to `GET /auth/callback` on the bot's API with a `code`.
3. The callback exchanges the code for a Discord access token, fetches the user's guild list from Discord's API, intersects it with `client.guilds` (guilds the bot is actually in) filtered to guilds where the user has `MANAGE_GUILD` permission, creates a server-side session, and returns a session cookie/token to the frontend.
4. All subsequent dashboard calls (`/guilds/{id}/config`, `/guilds/{id}/resend`) require that session and re-check the user still has `MANAGE_GUILD` on that specific guild before acting. The backend never trusts the frontend's claim of which guild it's managing — it re-verifies against Discord/bot state on every privileged call.

## Storage

Move from flat JSON files (`channel_config.json`, `last_article.json`) to SQLite, via a new `db.py` replacing `storage.py`. Single embedded DB file, no separate service to run, real transactions instead of read-modify-write races on JSON.

Tables:

- `guild_config` (guild_id, game, channel_id) — replaces `channel_config.json`
- `patch_notes_cache` (game, article_url, content, content_type, fetched_at) — replaces `last_article.json` and additionally stores the actual article body/content so resend doesn't require rescraping
- `sessions` (session_id, discord_user_id, access_token, expires_at)

## Endpoints (this phase)

- `GET /auth/login`, `GET /auth/callback`, `POST /auth/logout`
- `GET /guilds` — guilds the logged-in user administers that the bot is also in
- `GET /guilds/{id}/config` / `PUT /guilds/{id}/config` — get/set the patch-notes channel
- `POST /guilds/{id}/resend` — resend the cached latest patch notes to the configured channel
- `GET /stats` — kept as-is, public, no auth

## Error Handling

Standard FastAPI `HTTPException` with a consistent JSON error shape:

- `401` — no/expired session
- `403` — user does not administer this guild, or bot is not in this guild
- `404` — no channel configured for this guild/game
- `502` — Discord API call or `channel.send()` failure

## Testing

Unit tests (via `pytest`, newly added) for:

- The SQLite access layer (`db.py`)
- Permission-checking logic (does this user administer this guild) using a fake guild list — no live bot connection needed

The OAuth callback and actual `channel.send()` calls are thin wrappers around Discord's API and are best verified manually against a test Discord server, consistent with this bot's current testing approach (no test framework is wired up yet beyond `test_scraper.py`).

## Out of Scope (future sub-projects)

- Additional admin features beyond channel config + resend
- Any UI/frontend implementation details (this spec is backend/API only)
- Migration tooling for existing `channel_config.json` / `last_article.json` data into SQLite (small enough to handle as a one-off script when implementing)
