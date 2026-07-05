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

def set_channel(guild_id: int, game: str, channel_id: int):
    """Set the channel ID for a specific game in a server."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO guild_config (guild_id, game, channel_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, game) DO UPDATE SET channel_id=excluded.channel_id
            """,
            (str(guild_id), game, str(channel_id)),
        )
        conn.commit()
    finally:
        conn.close()

def clear_channel(guild_id, game):
    """Clear the channel ID for a specific game in a server."""
    conn = get_connection()
    try:
        conn.execute(
            """
            DELETE FROM guild_config
            WHERE guild_id = ? AND game = ?
            """,
            (str(guild_id), game)
        )
        conn.commit()
    finally:
        conn.close()

def get_channel(guild_id, game):
    """Get the channel ID for a specific game in a server."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT channel_id FROM guild_config
            WHERE guild_id = ? AND game = ?
            """,
            (str(guild_id), game)
        ).fetchone()
        return int(row["channel_id"]) if row else None
    finally:
        conn.close()