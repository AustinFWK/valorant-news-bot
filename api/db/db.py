import os
import datetime

from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DB_FILE = os.environ.get("BOT_DB_FILE", "bot.db")

Base = declarative_base()


class GuildConfig(Base):
    __tablename__ = "guild_config"

    guild_id = Column(String, primary_key=True)
    game = Column(String, primary_key=True)
    channel_id = Column(String, nullable=False)


class PatchNotesCache(Base):
    __tablename__ = "patch_notes_cache"

    game = Column(String, primary_key=True)
    article_url = Column(String, nullable=False)
    content = Column(String, nullable=True)
    content_type = Column(String, nullable=False)
    fetched_at = Column(DateTime, nullable=False)


def get_engine():
    """Create an engine bound to the current DB_FILE.

    Built fresh on every call (rather than cached at import time) so tests
    can monkeypatch DB_FILE and get an isolated database, matching the
    pattern the old sqlite3-based get_connection() used.
    """
    return create_engine(f"sqlite:///{DB_FILE}")


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_db():
    Base.metadata.create_all(get_engine())


def set_channel(guild_id, game, channel_id):
    """Set the channel ID for a specific game in a server."""
    session = get_session()
    try:
        existing = session.get(GuildConfig, (str(guild_id), game))
        if existing:
            existing.channel_id = str(channel_id)
        else:
            session.add(GuildConfig(guild_id=str(guild_id), game=game, channel_id=str(channel_id)))
        session.commit()
    finally:
        session.close()


def clear_channel(guild_id, game):
    """Clear the channel ID for a specific game in a server."""
    session = get_session()
    try:
        existing = session.get(GuildConfig, (str(guild_id), game))
        if existing:
            session.delete(existing)
            session.commit()
    finally:
        session.close()


def get_channel(guild_id, game):
    """Get the channel ID for a specific game in a server."""
    session = get_session()
    try:
        row = session.get(GuildConfig, (str(guild_id), game))
        return int(row.channel_id) if row else None
    finally:
        session.close()


def set_cached_patch_notes(game, article_url, content, content_type):
    """Store the latest fetched patch notes for a game, replacing any prior cache entry."""
    session = get_session()
    try:
        fetched_at = datetime.datetime.now(datetime.timezone.utc)
        existing = session.get(PatchNotesCache, game)
        if existing:
            existing.article_url = article_url
            existing.content = content
            existing.content_type = content_type
            existing.fetched_at = fetched_at
        else:
            session.add(PatchNotesCache(
                game=game,
                article_url=article_url,
                content=content,
                content_type=content_type,
                fetched_at=fetched_at,
            ))
        session.commit()
    finally:
        session.close()


def get_cached_patch_notes(game):
    """Return (content, article_url, content_type) for the last cached patch notes, or None."""
    session = get_session()
    try:
        row = session.get(PatchNotesCache, game)
        if row is None:
            return None
        return row.content, row.article_url, row.content_type
    finally:
        session.close()


def get_last_article_url(game):
    """Return just the cached article URL for a game, or None."""
    cached = get_cached_patch_notes(game)
    return cached[1] if cached else None
