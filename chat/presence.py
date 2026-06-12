import logging
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


def set_presence(user_id: int) -> None:
    """Mark user as online with TTL = presence_grace_seconds."""
    client = _get_redis()
    if client is None:
        return
    ttl = settings.PRESENCE_GRACE_SECONDS
    key = f"presence:{user_id}"
    try:
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        client.setex(key, ttl, now_iso)
    except Exception as e:
        logger.debug("Presence set failed: %s", e)


def delete_presence(user_id: int) -> None:
    """Remove presence key on explicit disconnect."""
    client = _get_redis()
    if client is None:
        return
    try:
        client.delete(f"presence:{user_id}")
    except Exception as e:
        logger.debug("Presence delete failed: %s", e)


def get_presence_data(user_id: int) -> dict:
    """Return {'connected': bool, 'last_seen': iso str or None}."""
    client = _get_redis()
    if client is None:
        return {"connected": False, "last_seen": None}
    try:
        val = client.get(f"presence:{user_id}")
        if val is None:
            return {"connected": False, "last_seen": None}
        return {"connected": True, "last_seen": val}
    except Exception as e:
        logger.debug("Presence get failed: %s", e)
        return {"connected": False, "last_seen": None}
