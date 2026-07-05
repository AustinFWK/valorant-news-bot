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