"""Presence is tracked per connection so multi-tab users stay online until the
last connection drops. Backed by fakeredis — no live Redis needed."""
import time

import fakeredis
import pytest
from django.test import override_settings

from chat import presence


@pytest.fixture
def fake_redis(monkeypatch):
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(presence, "_get_redis", lambda: client)
    return client


@override_settings(PRESENCE_GRACE_SECONDS=15)
def test_two_tabs_one_drops_user_stays_online(fake_redis):
    presence.set_presence(1, "chan-A")
    presence.set_presence(1, "chan-B")
    assert presence.get_presence_data(1)["connected"] is True

    presence.delete_presence(1, "chan-A")  # one tab closes — the bug case
    assert presence.get_presence_data(1)["connected"] is True

    presence.delete_presence(1, "chan-B")  # last tab closes
    assert presence.get_presence_data(1)["connected"] is False


@override_settings(PRESENCE_GRACE_SECONDS=15)
def test_expired_connection_pruned_live_one_kept(fake_redis):
    presence.set_presence(1, "live")
    fake_redis.zadd("presence:1", {"stale": time.time() - 5})  # already past expiry
    assert presence.get_presence_data(1)["connected"] is True
    assert fake_redis.zscore("presence:1", "stale") is None


@override_settings(PRESENCE_GRACE_SECONDS=15)
def test_all_connections_expired_marks_offline(fake_redis):
    fake_redis.zadd("presence:1", {"a": time.time() - 1, "b": time.time() - 2})
    assert presence.get_presence_data(1)["connected"] is False


@override_settings(PRESENCE_GRACE_SECONDS=15)
def test_last_seen_persists_after_disconnect(fake_redis):
    presence.set_presence(1, "chan-A")
    presence.delete_presence(1, "chan-A")
    data = presence.get_presence_data(1)
    assert data["connected"] is False
    assert data["last_seen"] is not None
