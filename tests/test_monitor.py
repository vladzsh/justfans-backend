"""Task 3.4: Monitor snapshot endpoint — shape and role-access tests."""
import pytest

from chat.services import create_message
from chat.models import Message


@pytest.mark.django_db
def test_teamlead_can_get_monitor_snapshot(client, teamlead, chatter, conversation):
    client.force_login(teamlead)
    response = client.get("/api/monitor/snapshot/")
    assert response.status_code == 200
    data = response.json()

    assert "chatters" in data
    chatters = data["chatters"]
    assert len(chatters) >= 1

    entry = next((c for c in chatters if c["id"] == chatter.id), None)
    assert entry is not None
    assert "connected" in entry
    assert "last_seen" in entry
    assert "dialogs_count" in entry
    assert "waiting" in entry
    assert entry["dialogs_count"] == 1
    assert isinstance(entry["waiting"], list)


@pytest.mark.django_db
def test_monitor_snapshot_waiting_list_populated(client, teamlead, chatter, conversation):
    """After a fan sends a message, chatter appears in waiting list."""
    create_message(
        conversation_id=conversation.id,
        sender=Message.SENDER_FAN,
        text="please reply",
    )

    client.force_login(teamlead)
    response = client.get("/api/monitor/snapshot/")
    assert response.status_code == 200
    data = response.json()

    entry = next(c for c in data["chatters"] if c["id"] == chatter.id)
    assert len(entry["waiting"]) == 1
    assert entry["waiting"][0]["conversation_id"] == conversation.id
    assert "waiting_since" in entry["waiting"][0]
    assert "fan_name" in entry["waiting"][0]
