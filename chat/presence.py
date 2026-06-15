import logging
import time
from datetime import datetime, timezone

import redis as redis_lib
from django.conf import settings

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        _redis_client = client
        return client
    except Exception:
        return None


def set_presence(user_id: int, channel_name: str) -> None:
    """Mark one connection of a user as online and refresh last seen.

    Presence is tracked per connection (Redis sorted set, member = WS channel,
    score = expiry timestamp) so a user with several open tabs stays online
    until the *last* connection drops. Each call also prunes expired members.
    """
    client = _get_redis()
    if client is None:
        return
    ttl = settings.PRESENCE_GRACE_SECONDS
    presence_key = f"presence:{user_id}"
    last_seen_key = f"last_seen:{user_id}"
    try:
        now = time.time()
        client.zadd(presence_key, {channel_name: now + ttl})
        client.zremrangebyscore(presence_key, "-inf", now)
        client.expire(presence_key, ttl)
        client.set(last_seen_key, datetime.now(tz=timezone.utc).isoformat())
    except Exception as e:
        logger.debug("Presence set failed: %s", e)


def delete_presence(user_id: int, channel_name: str) -> None:
    """Drop a single connection's presence on disconnect (other tabs survive)."""
    client = _get_redis()
    if client is None:
        return
    try:
        client.zrem(f"presence:{user_id}", channel_name)
    except Exception as e:
        logger.debug("Presence delete failed: %s", e)


def get_presence_data(user_id: int) -> dict:
    """Return {'connected': bool, 'last_seen': iso str or None}.

    Connected iff at least one non-expired connection remains.
    """
    client = _get_redis()
    if client is None:
        return {"connected": False, "last_seen": None}
    presence_key = f"presence:{user_id}"
    try:
        client.zremrangebyscore(presence_key, "-inf", time.time())
        is_connected = client.zcard(presence_key) > 0
        last_seen = client.get(f"last_seen:{user_id}")
        return {
            "connected": bool(is_connected),
            "last_seen": last_seen,
        }
    except Exception as e:
        logger.debug("Presence get failed: %s", e)
        return {"connected": False, "last_seen": None}
