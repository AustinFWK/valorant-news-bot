import pytest
from api.db import db


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