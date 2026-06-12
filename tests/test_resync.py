"""Task 4.3: Tests for /api/sync/ endpoint."""
import pytest

from chat.models import Message
from chat.services import create_message


@pytest.mark.django_db
def test_sync_returns_messages_after_id(client, chatter, conversation):
    m1 = create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Msg 1")
    m2 = create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Msg 2")
    m3 = create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Msg 3")

    client.force_login(chatter)
    resp = client.get(f"/api/sync/?after_id={m1.id}")
    assert resp.status_code == 200
    data = resp.json()

    returned_ids = [m["id"] for m in data["messages"]]
    assert m1.id not in returned_ids
    assert m2.id in returned_ids
    assert m3.id in returned_ids


@pytest.mark.django_db
def test_sync_messages_in_asc_order(client, chatter, conversation):
    for i in range(5):
        create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text=f"Msg {i}")

    client.force_login(chatter)
    resp = client.get("/api/sync/?after_id=0")
    data = resp.json()
    ids = [m["id"] for m in data["messages"]]
    assert ids == sorted(ids)


@pytest.mark.django_db
def test_sync_no_duplicates(client, chatter, conversation):
    m1 = create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Hello")
    m2 = create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="World")

    client.force_login(chatter)
    resp = client.get(f"/api/sync/?after_id={m1.id - 1}")
    data = resp.json()
    ids = [m["id"] for m in data["messages"]]
    assert len(ids) == len(set(ids))


@pytest.mark.django_db
def test_sync_only_own_conversations(client, chatter, chatter2, conversation, conversation2):
    m1 = create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Own")
    m2 = create_message(conversation_id=conversation2.id, sender=Message.SENDER_FAN, text="Other")

    client.force_login(chatter)
    resp = client.get("/api/sync/?after_id=0")
    data = resp.json()
    ids = [m["id"] for m in data["messages"]]
    assert m1.id in ids
    assert m2.id not in ids


@pytest.mark.django_db
def test_sync_includes_conversations_snapshot(client, chatter, conversation):
    client.force_login(chatter)
    resp = client.get("/api/sync/?after_id=0")
    data = resp.json()
    assert "conversations" in data
    conv_ids = [c["id"] for c in data["conversations"]]
    assert conversation.id in conv_ids


@pytest.mark.django_db
def test_messages_pagination_no_overlap(client, chatter, conversation):
    msgs = [
        create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text=f"M{i}")
        for i in range(10)
    ]

    client.force_login(chatter)
    resp1 = client.get(f"/api/conversations/{conversation.id}/messages/?limit=5")
    data1 = resp1.json()
    assert data1["has_more"] is True
    page1_ids = set(m["id"] for m in data1["results"])

    oldest_id = min(page1_ids)
    resp2 = client.get(f"/api/conversations/{conversation.id}/messages/?limit=5&before_id={oldest_id}")
    data2 = resp2.json()
    page2_ids = set(m["id"] for m in data2["results"])

    assert page1_ids.isdisjoint(page2_ids)
