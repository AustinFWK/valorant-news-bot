# Dashboard API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the website a dashboard where a Discord server admin can log in with Discord, set which channel receives Valorant patch notes for their server, and resend the last cached patch notes to that channel.

**Architecture:** A FastAPI app (new `api/` package) is mounted in the same process as the existing `discord.py` bot (`bot.py`), started via `uvicorn.Server.serve()` as an `asyncio` task inside `on_ready`, replacing the current raw `aiohttp` server. Config, patch-notes cache, and OAuth sessions move from flat JSON files (`storage.py`) into SQLite (`db.py`). Auth is Discord OAuth2: a "Login with Discord" button (frontend-only, out of scope here) hits `GET /auth/login`, which redirects to Discord; `GET /auth/callback` exchanges the code, creates a server-side session, and sets an httponly cookie. Every privileged endpoint re-verifies the session's user actually has `MANAGE_GUILD` on the target guild by calling Discord's API fresh — never trusting client-supplied guild claims.

**Tech Stack:** Python, `discord.py`, FastAPI, `uvicorn`, `aiohttp` (already a dependency, used for outbound Discord REST calls), `sqlite3` (stdlib), `pytest` (new, for the DB and permission-logic unit tests).

## Global Constraints

- The site (frontend) stays fully browsable without login; OAuth only starts when the user clicks "Login with Discord" (spec: Auth Flow section). This plan implements only the backend routes — no frontend work.
- Storage is SQLite, replacing `channel_config.json` and `last_article.json` (spec: Storage section).
- The API runs in the same process/VPS as the bot, not a separate service (spec: Architecture Decision).
- Every privileged call re-verifies `MANAGE_GUILD` against Discord/bot state on every request — never trust the frontend's claim of which guild it's managing (spec: Auth Flow, step 4).
- Resend must use the stored/cached patch notes content, not re-scrape (spec: Problem statement, Storage section).
- Error responses use a consistent JSON shape: `401` no/expired session, `403` not an admin of the guild or bot not in it, `404` no channel configured, `502` Discord API/send failure (spec: Error Handling).
- CORS allowed origins: `http://localhost:5173`, `https://patchyonline.xyz` (existing pattern in `bot.py:19`).

---

### Task 1: SQLite schema and guild-config functions in `db.py`

**Files:**
- Create: `db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `db.DB_FILE` (module-level path string), `db.init_db()`, `db.get_connection()`, `db.set_channel(guild_id, game, channel_id)`, `db.clear_channel(guild_id, game)`, `db.get_channel(guild_id, game) -> int | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/__init__.py` (empty file) and `tests/test_db.py`:

```python
import pytest
import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_FILE", db_file)
    db.init_db()
    yield db_file


def test_get_channel_returns_none_when_unset():
    assert db.get_channel(123, "valorant") is None


def test_set_and_get_channel():
    db.set_channel(123, "valorant", 456)
    assert db.get_channel(123, "valorant") == 456


def test_set_channel_overwrites_existing_value():
    db.set_channel(123, "valorant", 456)
    db.set_channel(123, "valorant", 789)
    assert db.get_channel(123, "valorant") == 789


def test_clear_channel_removes_entry():
    db.set_channel(123, "valorant", 456)
    db.clear_channel(123, "valorant")
    assert db.get_channel(123, "valorant") is None


def test_clear_channel_on_unset_entry_does_not_raise():
    db.clear_channel(123, "valorant")
    assert db.get_channel(123, "valorant") is None


def test_channels_are_isolated_per_guild():
    db.set_channel(123, "valorant", 456)
    db.set_channel(999, "valorant", 111)
    assert db.get_channel(123, "valorant") == 456
    assert db.get_channel(999, "valorant") == 111
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'db'` (or `AttributeError`, since `db.py` doesn't exist yet)

- [ ] **Step 3: Write `db.py`**

```python
import os
import sqlite3

DB_FILE = os.environ.get("BOT_DB_FILE", "bot.db")


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id TEXT NOT NULL,
                game TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                PRIMARY KEY (guild_id, game)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def set_channel(guild_id, game, channel_id):
    """Set the channel ID for a specific game in a guild."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO guild_config (guild_id, game, channel_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, game) DO UPDATE SET channel_id = excluded.channel_id
            """,
            (str(guild_id), game, str(channel_id)),
        )
        conn.commit()
    finally:
        conn.close()


def clear_channel(guild_id, game):
    """Clear the channel ID for a specific game in a guild."""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM guild_config WHERE guild_id = ? AND game = ?",
            (str(guild_id), game),
        )
        conn.commit()
    finally:
        conn.close()


def get_channel(guild_id, game):
    """Get the channel ID for a specific game in a guild."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT channel_id FROM guild_config WHERE guild_id = ? AND game = ?",
            (str(guild_id), game),
        ).fetchone()
        return int(row["channel_id"]) if row else None
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add db.py tests/__init__.py tests/test_db.py
git commit -m "feat: add SQLite guild_config table and channel accessors in db.py"
```

---

### Task 2: Patch-notes cache in `db.py`, wired into `bot.py`, and remove `storage.py`

**Files:**
- Modify: `db.py`
- Modify: `bot.py:9` (import), `bot.py:157-206` (`do_valorant_check`)
- Modify: `requirements.txt` (add `pytest`)
- Test: `tests/test_db.py`
- Delete: `storage.py`, `channel_config.json`, `last_article.json` (superseded by SQLite; see Task 3 for migrating any existing data first if this is a live deployment)

**Interfaces:**
- Consumes: `db.get_connection()`, `db.init_db()` from Task 1
- Produces: `db.set_cached_patch_notes(game, article_url, content, content_type)`, `db.get_cached_patch_notes(game) -> tuple[str | None, str, str] | None` (returns `(content, article_url, content_type)`), `db.get_last_article_url(game) -> str | None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_db.py`:

```python
def test_get_cached_patch_notes_returns_none_when_unset():
    assert db.get_cached_patch_notes("valorant") is None


def test_set_and_get_cached_patch_notes():
    db.set_cached_patch_notes("valorant", "https://example.com/a", "<p>hi</p>", "article")
    content, article_url, content_type = db.get_cached_patch_notes("valorant")
    assert content == "<p>hi</p>"
    assert article_url == "https://example.com/a"
    assert content_type == "article"


def test_set_cached_patch_notes_overwrites_existing_entry():
    db.set_cached_patch_notes("valorant", "https://example.com/a", "<p>old</p>", "article")
    db.set_cached_patch_notes("valorant", "https://example.com/b", "<p>new</p>", "article")
    content, article_url, content_type = db.get_cached_patch_notes("valorant")
    assert article_url == "https://example.com/b"
    assert content == "<p>new</p>"


def test_get_last_article_url_returns_none_when_unset():
    assert db.get_last_article_url("valorant") is None


def test_get_last_article_url_returns_cached_url():
    db.set_cached_patch_notes("valorant", "https://example.com/a", "<p>hi</p>", "article")
    assert db.get_last_article_url("valorant") == "https://example.com/a"


def test_cached_video_entry_has_null_content():
    db.set_cached_patch_notes("valorant", "https://youtube.com/watch?v=1", None, "video")
    content, article_url, content_type = db.get_cached_patch_notes("valorant")
    assert content is None
    assert content_type == "video"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `AttributeError: module 'db' has no attribute 'set_cached_patch_notes'`

- [ ] **Step 3: Add the patch-notes cache table and functions to `db.py`**

In `init_db()`, add a second `CREATE TABLE IF NOT EXISTS` call before `conn.commit()`:

```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS patch_notes_cache (
                game TEXT PRIMARY KEY,
                article_url TEXT NOT NULL,
                content TEXT,
                content_type TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )
```

Add to the top of `db.py`:

```python
import datetime
```

Append these functions to `db.py`:

```python
def set_cached_patch_notes(game, article_url, content, content_type):
    """Store the latest fetched patch notes for a game, replacing any prior cache entry."""
    conn = get_connection()
    try:
        fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO patch_notes_cache (game, article_url, content, content_type, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(game) DO UPDATE SET
                article_url = excluded.article_url,
                content = excluded.content,
                content_type = excluded.content_type,
                fetched_at = excluded.fetched_at
            """,
            (game, article_url, content, content_type, fetched_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_patch_notes(game):
    """Return (content, article_url, content_type) for the last cached patch notes, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT article_url, content, content_type FROM patch_notes_cache WHERE game = ?",
            (game,),
        ).fetchone()
        if row is None:
            return None
        return row["content"], row["article_url"], row["content_type"]
    finally:
        conn.close()


def get_last_article_url(game):
    """Return just the cached article URL for a game, or None."""
    cached = get_cached_patch_notes(game)
    return cached[1] if cached else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Wire `db.py` into `bot.py`**

In `bot.py`, replace the import on line 9:

```python
from storage import clear_channel, get_last_article, set_channel, get_channel, set_last_article
```

with:

```python
import db
```

Add `db.init_db()` near the top of `bot.py`, right after the `client = commands.Bot(...)` line (`bot.py:15`):

```python
db.init_db()
```

Update the four command handlers that reference the old `storage` functions:

- `bot.py:73`: `set_channel(ctx.guild.id, game, ctx.channel.id)` → `db.set_channel(ctx.guild.id, game, ctx.channel.id)`
- `bot.py:88`: `clear_channel(ctx.guild.id, game)` → `db.clear_channel(ctx.guild.id, game)`
- `bot.py:95`: `channel_id = get_channel(ctx.guild.id, game)` → `channel_id = db.get_channel(ctx.guild.id, game)`

Update `do_valorant_check` (`bot.py:157-206`):

- `bot.py:166`: `last_url = get_last_article('valorant')` → `last_url = db.get_last_article_url('valorant')`
- `bot.py:173`: `set_last_article('valorant', current_url)` → remove this line entirely (the "first run" branch now just returns without caching, since there's no content to cache yet — the next real check will populate the cache when it fetches content)
- `bot.py:206`: `set_last_article('valorant', current_url)` → `db.set_cached_patch_notes('valorant', article_url, text_content, content_type)`

The full updated `do_valorant_check` should read:

```python
async def do_valorant_check():
    """ Check for a new article and post it if found. """

    try:
        current_url = get_latest_article_url()
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest article URL: {e}")
        return

    last_url = db.get_last_article_url('valorant')

    if current_url == last_url:
        return  # No new article

    if last_url is None:
        # First run: fetch and cache content now so the dashboard's "resend"
        # has something to send, without posting to any channel
        try:
            text_content, article_url, content_type = get_latest_patch_notes()
        except Exception as e:
            print(f"[ERROR] Failed to fetch article content: {e}")
            return
        db.set_cached_patch_notes('valorant', article_url, text_content, content_type)
        print(f"[INFO] Initialized tracking with {article_url}")
        return

    # New article detected — fetch content before saving URL so we can retry on failure
    print(f"[INFO] New article detected: {current_url}")
    try:
        text_content, article_url, content_type = get_latest_patch_notes()
    except Exception as e:
        print(f"[ERROR] Failed to fetch article content: {e}")
        return  # Don't save URL — will retry on next cycle

    for guild in client.guilds:
        channel_id = db.get_channel(guild.id, 'valorant')
        if channel_id is None:
            continue

        channel = client.get_channel(channel_id)
        if not channel:
            continue

        try:
            if content_type == 'video':
                await channel.send(f"🔗 New Valorant video posted! : {article_url}")
            else:
                chunks = smart_chunk(text_content)
                for chunk in chunks:
                    await channel.send(chunk)
                await channel.send(f"\n\n🔗 Full article: {article_url}")
        except Exception as e:
            print(f"[ERROR] Failed to post to {guild.name}: {e}")

    # Save cache only after posting has been attempted for all guilds
    db.set_cached_patch_notes('valorant', article_url, text_content, content_type)
```

- [ ] **Step 6: Delete `storage.py`**

```bash
rm storage.py
```

- [ ] **Step 7: Add `pytest` to `requirements.txt`**

Append to `requirements.txt`:

```
pytest==8.3.4
```

- [ ] **Step 8: Run the full test suite to confirm nothing broke**

Run: `pytest tests/ -v`
Expected: PASS (12 tests — `bot.py` isn't under test, so this just confirms `db.py` is self-consistent)

- [ ] **Step 9: Commit**

```bash
git add db.py bot.py requirements.txt tests/test_db.py
git rm storage.py
git commit -m "feat: cache full patch-notes content in SQLite, replacing storage.py"
```

---

### Task 3: One-off migration script for existing JSON data

**Files:**
- Create: `scripts/migrate_json_to_sqlite.py`

**Interfaces:**
- Consumes: `db.init_db()`, `db.set_channel()`, `db.set_cached_patch_notes()` from Tasks 1–2

This task only matters if `channel_config.json` and/or `last_article.json` exist from a prior deployment. It's a manual, one-time script — not part of the app's runtime path.

- [ ] **Step 1: Write the migration script**

```python
"""One-off script: migrate channel_config.json / last_article.json into bot.db.

Run once, before starting the bot on the new SQLite-backed code:
    python scripts/migrate_json_to_sqlite.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

CHANNEL_CONFIG_FILE = "channel_config.json"
LAST_ARTICLE_FILE = "last_article.json"


def migrate_channel_config():
    if not os.path.exists(CHANNEL_CONFIG_FILE):
        print(f"[SKIP] {CHANNEL_CONFIG_FILE} not found")
        return

    with open(CHANNEL_CONFIG_FILE, "r") as f:
        config = json.load(f)

    count = 0
    for guild_id, games in config.items():
        for game, channel_id in games.items():
            db.set_channel(guild_id, game, channel_id)
            count += 1

    print(f"[OK] Migrated {count} guild/game channel entries")


def migrate_last_article():
    if not os.path.exists(LAST_ARTICLE_FILE):
        print(f"[SKIP] {LAST_ARTICLE_FILE} not found")
        return

    with open(LAST_ARTICLE_FILE, "r") as f:
        data = json.load(f)

    count = 0
    for game, article_url in data.items():
        # No cached content available from the old format — store the URL only.
        # The next check_for_updates cycle will populate real content once a
        # new article is detected, or an admin can trigger a manual /patchnotes
        # to warm the cache.
        db.set_cached_patch_notes(game, article_url, None, "article")
        count += 1

    print(f"[OK] Migrated {count} last-article URL entries (content not backfilled)")


if __name__ == "__main__":
    db.init_db()
    migrate_channel_config()
    migrate_last_article()
    print("[DONE] Migration complete")
```

- [ ] **Step 2: Verify manually**

This isn't unit-tested — it's a one-shot data migration run by hand against real deployment files. Verify by running it against a copy of production `channel_config.json`/`last_article.json` in a scratch directory and checking `bot.db` afterward:

```bash
sqlite3 bot.db "SELECT * FROM guild_config;"
sqlite3 bot.db "SELECT game, article_url, content_type FROM patch_notes_cache;"
```

Expected: rows matching the source JSON files' contents.

- [ ] **Step 3: Commit**

```bash
mkdir -p scripts
git add scripts/migrate_json_to_sqlite.py
git commit -m "chore: add one-off script to migrate JSON config into SQLite"
```

---

### Task 4: OAuth sessions table and functions in `db.py`

**Files:**
- Modify: `db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `db.get_connection()` from Task 1
- Produces: `db.SESSION_TTL_SECONDS` (int constant), `db.create_session(discord_user_id, access_token, ttl_seconds=SESSION_TTL_SECONDS) -> str`, `db.get_session(session_id) -> dict | None` (dict has keys `discord_user_id`, `access_token`), `db.delete_session(session_id)`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_db.py`:

```python
import datetime


def test_create_session_returns_a_token_and_get_session_returns_it():
    session_id = db.create_session("user-1", "access-token-abc")
    session = db.get_session(session_id)
    assert session["discord_user_id"] == "user-1"
    assert session["access_token"] == "access-token-abc"


def test_get_session_returns_none_for_unknown_id():
    assert db.get_session("does-not-exist") is None


def test_delete_session_removes_it():
    session_id = db.create_session("user-1", "access-token-abc")
    db.delete_session(session_id)
    assert db.get_session(session_id) is None


def test_delete_session_on_unknown_id_does_not_raise():
    db.delete_session("does-not-exist")


def test_expired_session_returns_none():
    session_id = db.create_session("user-1", "access-token-abc", ttl_seconds=-1)
    assert db.get_session(session_id) is None


def test_two_sessions_are_independent():
    id_a = db.create_session("user-a", "token-a")
    id_b = db.create_session("user-b", "token-b")
    assert db.get_session(id_a)["discord_user_id"] == "user-a"
    assert db.get_session(id_b)["discord_user_id"] == "user-b"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `AttributeError: module 'db' has no attribute 'create_session'`

- [ ] **Step 3: Add the sessions table and functions to `db.py`**

In `init_db()`, add a third `CREATE TABLE IF NOT EXISTS` call before `conn.commit()`:

```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                discord_user_id TEXT NOT NULL,
                access_token TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
```

Add to the top of `db.py`:

```python
import secrets
```

Append these to `db.py`:

```python
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def create_session(discord_user_id, access_token, ttl_seconds=SESSION_TTL_SECONDS):
    """Create a server-side session and return its opaque session_id."""
    conn = get_connection()
    try:
        session_id = secrets.token_urlsafe(32)
        expires_at = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=ttl_seconds)
        ).isoformat()
        conn.execute(
            "INSERT INTO sessions (session_id, discord_user_id, access_token, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, str(discord_user_id), access_token, expires_at),
        )
        conn.commit()
        return session_id
    finally:
        conn.close()


def get_session(session_id):
    """Return {"discord_user_id", "access_token"} for a valid, non-expired session, else None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT discord_user_id, access_token, expires_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None

        expires_at = datetime.datetime.fromisoformat(row["expires_at"])
        if expires_at < datetime.datetime.now(datetime.timezone.utc):
            delete_session(session_id)
            return None

        return {"discord_user_id": row["discord_user_id"], "access_token": row["access_token"]}
    finally:
        conn.close()


def delete_session(session_id):
    """Delete a session, if it exists."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS (18 tests)

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add SQLite-backed OAuth session storage to db.py"
```

---

### Task 5: OAuth config values and `api/discord_client.py`

**Files:**
- Modify: `config/config.py`
- Create: `api/__init__.py`
- Create: `api/discord_client.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `config.config.DISCORD_CLIENT_ID`, `config.config.DISCORD_CLIENT_SECRET`, `config.config.DISCORD_REDIRECT_URI`, `config.config.FRONTEND_URL`, `config.config.ALLOWED_ORIGINS` (list); `api.discord_client.exchange_code(code) -> dict`, `api.discord_client.fetch_user(access_token) -> dict`, `api.discord_client.fetch_user_guilds(access_token) -> list[dict]`

This task adds outbound HTTP calls to Discord's REST API. It has no meaningful unit-test surface (it's a thin wrapper around live HTTP calls) — per the spec's Testing section, this is verified manually against a real Discord OAuth app once Task 8 wires it into a working `/auth/callback`. No test step here; verification happens end-to-end in Task 8.

- [ ] **Step 1: Add OAuth config values to `config/config.py`**

Append to `config/config.py`:

```python
# Discord OAuth (dashboard login)
DISCORD_CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.environ.get('DISCORD_REDIRECT_URI')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://patchyonline.xyz')
ALLOWED_ORIGINS = ["http://localhost:5173", "https://patchyonline.xyz"]
```

- [ ] **Step 2: Add the new env vars to `.env` (locally) and note them for deployment**

Add these keys (with real values from the Discord Developer Portal's OAuth2 page) to your local `.env`:

```
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_REDIRECT_URI=http://localhost:8080/auth/callback
```

`.env` is already gitignored (it holds `DISCORD_TOKEN` today) — do not commit it.

- [ ] **Step 3: Create the `api` package**

```bash
mkdir -p api
touch api/__init__.py
```

- [ ] **Step 4: Write `api/discord_client.py`**

```python
import aiohttp

from config.config import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI

DISCORD_API_BASE = "https://discord.com/api/v10"


async def exchange_code(code):
    """Exchange an OAuth authorization code for an access token."""
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{DISCORD_API_BASE}/oauth2/token", data=data) as resp:
            resp.raise_for_status()
            return await resp.json()


async def fetch_user(access_token):
    """Fetch the logged-in Discord user's profile."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DISCORD_API_BASE}/users/@me", headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()


async def fetch_user_guilds(access_token):
    """Fetch the guilds the logged-in Discord user belongs to."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()
```

- [ ] **Step 5: Commit**

```bash
git add config/config.py api/__init__.py api/discord_client.py
git commit -m "feat: add Discord OAuth config and REST client for token/user/guilds"
```

---

### Task 6: Permission logic in `api/permissions.py`

**Files:**
- Create: `api/permissions.py`
- Test: `tests/test_permissions.py`

**Interfaces:**
- Produces: `api.permissions.has_manage_guild(user_guild: dict) -> bool`, `api.permissions.get_manageable_guild_ids(user_guilds: list[dict], bot_guild_ids: set[str]) -> set[str]`

This is the logic that decides whether a logged-in Discord user is allowed to administer a given guild's config — the core of the "never trust the frontend's claim" requirement.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_permissions.py`:

```python
from api.permissions import has_manage_guild, get_manageable_guild_ids

MANAGE_GUILD_BIT = 0x20


def test_has_manage_guild_true_when_permission_bit_set():
    user_guild = {"id": "1", "owner": False, "permissions": str(MANAGE_GUILD_BIT)}
    assert has_manage_guild(user_guild) is True


def test_has_manage_guild_false_when_permission_bit_not_set():
    user_guild = {"id": "1", "owner": False, "permissions": "0"}
    assert has_manage_guild(user_guild) is False


def test_has_manage_guild_true_when_owner_even_without_bit():
    user_guild = {"id": "1", "owner": True, "permissions": "0"}
    assert has_manage_guild(user_guild) is True


def test_has_manage_guild_true_when_other_bits_also_set():
    # e.g. MANAGE_GUILD (0x20) plus some other permission bit (0x8)
    user_guild = {"id": "1", "owner": False, "permissions": str(MANAGE_GUILD_BIT | 0x8)}
    assert has_manage_guild(user_guild) is True


def test_get_manageable_guild_ids_filters_to_bot_guilds_user_administers():
    user_guilds = [
        {"id": "1", "owner": False, "permissions": str(MANAGE_GUILD_BIT)},  # admin, bot in it
        {"id": "2", "owner": False, "permissions": "0"},                    # not admin
        {"id": "3", "owner": True, "permissions": "0"},                     # owner, bot not in it
    ]
    bot_guild_ids = {"1", "4"}
    assert get_manageable_guild_ids(user_guilds, bot_guild_ids) == {"1"}


def test_get_manageable_guild_ids_empty_when_no_overlap():
    user_guilds = [{"id": "1", "owner": False, "permissions": str(MANAGE_GUILD_BIT)}]
    bot_guild_ids = {"999"}
    assert get_manageable_guild_ids(user_guilds, bot_guild_ids) == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_permissions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api.permissions'`

- [ ] **Step 3: Write `api/permissions.py`**

```python
MANAGE_GUILD = 0x20


def has_manage_guild(user_guild):
    """Return True if the Discord user has MANAGE_GUILD on this guild (owner always qualifies).

    `user_guild` is one entry from Discord's GET /users/@me/guilds response:
    a dict with at least "owner" (bool) and "permissions" (stringified int bitfield).
    """
    if user_guild.get("owner"):
        return True

    permissions = int(user_guild.get("permissions", 0))
    return (permissions & MANAGE_GUILD) == MANAGE_GUILD


def get_manageable_guild_ids(user_guilds, bot_guild_ids):
    """Return the set of guild id strings the user administers AND the bot is also in.

    `user_guilds` is the list from Discord's GET /users/@me/guilds response.
    `bot_guild_ids` is a set of guild id strings the bot is currently in.
    """
    manageable = {g["id"] for g in user_guilds if has_manage_guild(g)}
    return manageable & set(bot_guild_ids)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_permissions.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add api/permissions.py tests/test_permissions.py
git commit -m "feat: add MANAGE_GUILD permission-checking logic"
```

---

### Task 7: FastAPI app skeleton, `/stats` ported, mounted into `bot.py`

**Files:**
- Create: `api/app.py`
- Modify: `bot.py:1-33` (imports, remove aiohttp app/handler), `bot.py:39-51` (`on_ready`)
- Modify: `requirements.txt` (add `fastapi`, `uvicorn`)

**Interfaces:**
- Consumes: `config.config.ALLOWED_ORIGINS` from Task 5
- Produces: `api.app.create_app(client) -> FastAPI` — the factory every later route module plugs into via `app.include_router(...)`

This task replaces the current raw `aiohttp` server with FastAPI, keeping `/stats` working identically, before any auth/guild routes exist. This keeps the cutover to FastAPI itself independently verifiable.

- [ ] **Step 1: Add FastAPI and uvicorn to `requirements.txt`**

Append to `requirements.txt`:

```
fastapi==0.115.6
uvicorn==0.34.0
```

- [ ] **Step 2: Install and write `api/app.py`**

```bash
pip install fastapi==0.115.6 uvicorn==0.34.0
```

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.config import ALLOWED_ORIGINS


def create_app(client):
    """Build the FastAPI app. `client` is the live discord.py Bot instance."""
    app = FastAPI(title="Patchy Bot API")
    app.state.discord_client = client

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/stats")
    async def stats():
        return {
            "servers": len(client.guilds),
            "members": sum(guild.member_count for guild in client.guilds),
        }

    return app
```

- [ ] **Step 3: Replace the aiohttp server in `bot.py`**

Remove the aiohttp import (`bot.py:1`) and the `--- Endpoints ---` block (`bot.py:17-33`):

```python
import aiohttp.web
```

and

```python
# --- Endpoints --- 
async def stats_handler(_request):
    Allowed_Origins = ["http://localhost:5173", "https://patchyonline.xyz"]
    origin = _request.headers.get('Origin', "")
    allowed = origin if origin in Allowed_Origins else Allowed_Origins[0]

    data = {
        "servers": len(client.guilds),
        "members": sum(guild.member_count for guild in client.guilds),
    }

    return aiohttp.web.json_response(data, headers={
        "Access-Control-Allow-Origin": allowed,
    })

app = aiohttp.web.Application()
app.router.add_get('/stats', stats_handler)
```

Add near the top of `bot.py`, alongside the other imports:

```python
import uvicorn
from api.app import create_app
```

Replace the `on_ready` handler (`bot.py:39-51`):

```python
@client.event
async def on_ready():
    print("The bot is ready for use")
    print("------------------------")

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("HTTP server started on port 8080")

    if not check_for_updates.is_running():
        check_for_updates.start()
```

with:

```python
@client.event
async def on_ready():
    print("The bot is ready for use")
    print("------------------------")

    fastapi_app = create_app(client)
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    client.loop.create_task(server.serve())
    print("HTTP server started on port 8080")

    if not check_for_updates.is_running():
        check_for_updates.start()
```

- [ ] **Step 4: Manually verify `/stats` still works**

Run: `python bot.py` (with a valid `DISCORD_TOKEN` in `.env`)

In another terminal:

```bash
curl -H "Origin: http://localhost:5173" http://localhost:8080/stats
```

Expected: JSON like `{"servers":1,"members":5}` and an `access-control-allow-origin: http://localhost:5173` response header.

- [ ] **Step 5: Commit**

```bash
git add api/app.py bot.py requirements.txt
git commit -m "feat: replace aiohttp server with FastAPI, port /stats endpoint"
```

---

### Task 8: `/auth/login`, `/auth/callback`, `/auth/logout`

**Files:**
- Create: `api/auth.py`
- Modify: `api/app.py` (include the auth router)

**Interfaces:**
- Consumes: `api.discord_client.exchange_code`, `fetch_user` (Task 5); `db.create_session`, `db.get_session`, `db.delete_session`, `db.SESSION_TTL_SECONDS` (Task 4); `config.config.DISCORD_CLIENT_ID`, `DISCORD_REDIRECT_URI`, `FRONTEND_URL` (Task 5)
- Produces: `api.auth.router` (FastAPI `APIRouter`), `api.auth.get_current_session(request: Request) -> dict` (FastAPI dependency — raises `HTTPException(401)` if missing/expired; returns `{"discord_user_id", "access_token"}`)

No unit tests here — this is a thin FastAPI routing layer around a live OAuth handshake and cookie handling; correctness is verified manually against a real Discord OAuth app, per the spec's Testing section.

- [ ] **Step 1: Write `api/auth.py`**

```python
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

import db
from api.discord_client import exchange_code, fetch_user
from config.config import DISCORD_CLIENT_ID, DISCORD_REDIRECT_URI, FRONTEND_URL

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
SESSION_COOKIE = "session_id"


@router.get("/login")
async def login():
    """Redirect the browser to Discord's OAuth consent screen."""
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
    }
    return RedirectResponse(url=f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}")


@router.get("/callback")
async def callback(code: str):
    """Handle Discord's OAuth redirect: exchange the code, create a session, set the cookie."""
    token_data = await exchange_code(code)
    access_token = token_data["access_token"]

    user = await fetch_user(access_token)
    session_id = db.create_session(user["id"], access_token)

    response = RedirectResponse(url=FRONTEND_URL)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=db.SESSION_TTL_SECONDS,
    )
    return response


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Delete the current session and clear its cookie."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        db.delete_session(session_id)
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "logged_out"}


def get_current_session(request: Request):
    """FastAPI dependency: return the current session dict, or raise 401."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Session expired")

    return session
```

- [ ] **Step 2: Register the auth router in `api/app.py`**

Add the import at the top of `api/app.py`:

```python
from api.auth import router as auth_router
```

Add before the `return app` line:

```python
    app.include_router(auth_router)
```

- [ ] **Step 3: Manually verify the OAuth flow**

Requires a Discord application configured in the Developer Portal with redirect URI `http://localhost:8080/auth/callback` and `DISCORD_CLIENT_ID`/`DISCORD_CLIENT_SECRET`/`DISCORD_REDIRECT_URI` set in `.env`.

Run: `python bot.py`, then visit `http://localhost:8080/auth/login` in a browser.

Expected: redirected to Discord's consent screen, then back to `FRONTEND_URL` with a `session_id` cookie set (check via browser devtools → Application → Cookies).

- [ ] **Step 4: Commit**

```bash
git add api/auth.py api/app.py
git commit -m "feat: add Discord OAuth login/callback/logout routes"
```

---

### Task 9: `GET /guilds`

**Files:**
- Create: `api/guilds.py`
- Modify: `api/app.py` (include the guilds router)

**Interfaces:**
- Consumes: `api.auth.get_current_session` (Task 8); `api.discord_client.fetch_user_guilds` (Task 5); `api.permissions.get_manageable_guild_ids` (Task 6)
- Produces: `api.guilds.router` (FastAPI `APIRouter`), `api.guilds.get_client(request) -> discord.Client` (dependency reading `request.app.state.discord_client`)

- [ ] **Step 1: Write `api/guilds.py`**

```python
from fastapi import APIRouter, Depends, Request

from api.auth import get_current_session
from api.discord_client import fetch_user_guilds
from api.permissions import get_manageable_guild_ids

router = APIRouter(prefix="/guilds", tags=["guilds"])


def get_client(request: Request):
    return request.app.state.discord_client


@router.get("")
async def list_guilds(session=Depends(get_current_session), client=Depends(get_client)):
    """List guilds the logged-in user administers that the bot is also in."""
    user_guilds = await fetch_user_guilds(session["access_token"])
    bot_guild_ids = {str(g.id) for g in client.guilds}
    manageable_ids = get_manageable_guild_ids(user_guilds, bot_guild_ids)

    return [
        {"id": str(g.id), "name": g.name}
        for g in client.guilds
        if str(g.id) in manageable_ids
    ]
```

- [ ] **Step 2: Register the guilds router in `api/app.py`**

Add the import at the top of `api/app.py`:

```python
from api.guilds import router as guilds_router
```

Add before the `return app` line:

```python
    app.include_router(guilds_router)
```

- [ ] **Step 3: Manually verify**

With a valid `session_id` cookie from Task 8's flow:

```bash
curl -H "Cookie: session_id=<value>" http://localhost:8080/guilds
```

Expected: JSON array of `{"id": ..., "name": ...}` for guilds you administer where the bot is also present. Without a cookie: `curl http://localhost:8080/guilds` → `401` with `{"error": "Not authenticated"}`.

- [ ] **Step 4: Commit**

```bash
git add api/guilds.py api/app.py
git commit -m "feat: add GET /guilds endpoint"
```

---

### Task 10: `GET`/`PUT /guilds/{guild_id}/config`

**Files:**
- Modify: `api/guilds.py`

**Interfaces:**
- Consumes: `db.get_channel`, `db.set_channel` (Task 1); `get_manageable_guild_ids` (Task 6)
- Produces: `api.guilds.require_guild_access(guild_id, session, client) -> discord.Guild` (raises `HTTPException(403)` if the bot isn't in the guild or the user doesn't administer it) — reused by Task 11

- [ ] **Step 1: Add the shared access check and config routes to `api/guilds.py`**

Add imports at the top of `api/guilds.py`:

```python
from fastapi import HTTPException
from pydantic import BaseModel

import db
```

Append below `list_guilds`:

```python
async def require_guild_access(guild_id, session, client):
    """Raise 403 unless the bot is in this guild and the session's user administers it."""
    guild = client.get_guild(int(guild_id))
    if guild is None:
        raise HTTPException(status_code=403, detail="Bot is not in this guild")

    user_guilds = await fetch_user_guilds(session["access_token"])
    manageable_ids = get_manageable_guild_ids(user_guilds, {str(guild.id)})
    if str(guild.id) not in manageable_ids:
        raise HTTPException(status_code=403, detail="You do not administer this guild")

    return guild


class ChannelConfigIn(BaseModel):
    game: str = "valorant"
    channel_id: str


@router.get("/{guild_id}/config")
async def get_config(
    guild_id: str,
    game: str = "valorant",
    session=Depends(get_current_session),
    client=Depends(get_client),
):
    await require_guild_access(guild_id, session, client)

    channel_id = db.get_channel(guild_id, game)
    if channel_id is None:
        raise HTTPException(status_code=404, detail="No channel configured")

    return {"game": game, "channel_id": str(channel_id)}


@router.put("/{guild_id}/config")
async def set_config(
    guild_id: str,
    body: ChannelConfigIn,
    session=Depends(get_current_session),
    client=Depends(get_client),
):
    guild = await require_guild_access(guild_id, session, client)

    channel = guild.get_channel(int(body.channel_id))
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found in this guild")

    db.set_channel(guild_id, body.game, body.channel_id)
    return {"game": body.game, "channel_id": body.channel_id}
```

- [ ] **Step 2: Manually verify**

```bash
curl -H "Cookie: session_id=<value>" "http://localhost:8080/guilds/<guild_id>/config?game=valorant"
```

Expected before any config is set: `404` with `{"error": "No channel configured"}`.

```bash
curl -X PUT -H "Cookie: session_id=<value>" -H "Content-Type: application/json" \
  -d '{"game":"valorant","channel_id":"<real_channel_id>"}' \
  "http://localhost:8080/guilds/<guild_id>/config"
```

Expected: `200` with `{"game":"valorant","channel_id":"<real_channel_id>"}`, and a follow-up `GET` returns the same value.

- [ ] **Step 3: Commit**

```bash
git add api/guilds.py
git commit -m "feat: add GET/PUT /guilds/{id}/config endpoints"
```

---

### Task 11: `POST /guilds/{guild_id}/resend`

**Files:**
- Modify: `api/guilds.py`
- Modify: `bot.py` (no code change — confirms `smart_chunk` is importable from `api/guilds.py`)

**Interfaces:**
- Consumes: `db.get_channel`, `db.get_cached_patch_notes` (Tasks 1–2); `require_guild_access` (Task 10); `valorant.formatter.smart_chunk`

- [ ] **Step 1: Add the resend route to `api/guilds.py`**

Add this import at the top of `api/guilds.py`:

```python
import discord

from valorant.formatter import smart_chunk
```

Append at the end of `api/guilds.py`:

```python
@router.post("/{guild_id}/resend")
async def resend_patch_notes(
    guild_id: str,
    game: str = "valorant",
    session=Depends(get_current_session),
    client=Depends(get_client),
):
    guild = await require_guild_access(guild_id, session, client)

    channel_id = db.get_channel(guild_id, game)
    if channel_id is None:
        raise HTTPException(status_code=404, detail="No channel configured")

    channel = guild.get_channel(int(channel_id))
    if channel is None:
        raise HTTPException(status_code=404, detail="Configured channel no longer exists")

    cached = db.get_cached_patch_notes(game)
    if cached is None:
        raise HTTPException(status_code=404, detail="No cached patch notes available")

    content, article_url, content_type = cached

    try:
        if content_type == "video":
            await channel.send(f"🔗 New Valorant video posted! : {article_url}")
        else:
            chunks = smart_chunk(content)
            for chunk in chunks:
                await channel.send(chunk)
            await channel.send(f"\n\n🔗 Full article: {article_url}")
    except discord.HTTPException as e:
        raise HTTPException(status_code=502, detail=f"Failed to send message: {e}")

    return {"status": "sent", "channel_id": str(channel_id)}
```

- [ ] **Step 2: Manually verify**

With a channel already configured (Task 10) and at least one patch-notes cache entry present (from running the bot for real, or by calling `db.set_cached_patch_notes` directly in a Python shell for a quick manual test):

```bash
curl -X POST -H "Cookie: session_id=<value>" "http://localhost:8080/guilds/<guild_id>/resend?game=valorant"
```

Expected: `200` with `{"status":"sent","channel_id":"<channel_id>"}`, and the message actually appears in the configured Discord channel.

- [ ] **Step 3: Commit**

```bash
git add api/guilds.py
git commit -m "feat: add POST /guilds/{id}/resend endpoint using cached patch notes"
```

---

### Task 12: Consistent error JSON shape and README update

**Files:**
- Modify: `api/app.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing new

FastAPI's default `HTTPException` response body is `{"detail": "..."}`. The spec calls for a consistent JSON error shape across all endpoints — standardize on `{"error": "..."}` everywhere via a single exception handler, rather than relying on each route.

- [ ] **Step 1: Add a global exception handler in `api/app.py`**

Add these imports at the top of `api/app.py`:

```python
from fastapi import HTTPException
from fastapi.responses import JSONResponse
```

Add before the `return app` line:

```python
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
```

- [ ] **Step 2: Manually verify the shape is consistent**

```bash
curl http://localhost:8080/guilds
```

Expected: `401` with body exactly `{"error":"Not authenticated"}` (not `{"detail":...}`).

- [ ] **Step 3: Update `README.md` with the new setup steps**

Add a new section at the end of `README.md`:

```markdown
## Dashboard API setup

In addition to `DISCORD_TOKEN`, the dashboard API needs a Discord OAuth2 app (create one at the same Developer Portal application, under the "OAuth2" tab) with these `.env` values:

```
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_REDIRECT_URI=http://localhost:8080/auth/callback
FRONTEND_URL=http://localhost:5173
```

Add `DISCORD_REDIRECT_URI`'s value to the OAuth2 app's list of allowed redirect URIs in the Developer Portal, or the callback will fail.

If you're upgrading a bot that was already running with `channel_config.json`/`last_article.json`, run `python scripts/migrate_json_to_sqlite.py` once before starting the bot, to carry existing channel settings into `bot.db`.
```

- [ ] **Step 4: Run the full test suite one last time**

Run: `pytest tests/ -v`
Expected: PASS (18 tests total: 12 in `test_db.py`, 6 in `test_permissions.py`)

- [ ] **Step 5: Commit**

```bash
git add api/app.py README.md
git commit -m "feat: standardize API error responses, document dashboard API setup"
```
