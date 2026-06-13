"""Monitor snapshot endpoint — shape, role-access, and models aggregation tests."""
import pytest

from chat.models import ContentModel, Conversation, Fan, Message
from chat.services import build_models_snapshot, create_message


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


# --- build_models_snapshot unit tests ---


@pytest.mark.django_db
def test_build_models_snapshot_empty():
    """No content models → empty list."""
    result = build_models_snapshot()
    assert result == []


@pytest.mark.django_db
def test_build_models_snapshot_model_with_no_conversations(db):
    """A model with zero conversations appears with dialogs_count=0 and empty waiting."""
    model = ContentModel.objects.create(name="Nova", avatar="⭐")
    result = build_models_snapshot()
    assert len(result) == 1
    entry = result[0]
    assert entry["id"] == model.id
    assert entry["name"] == "Nova"
    assert entry["avatar"] == "⭐"
    assert entry["dialogs_count"] == 0
    assert entry["waiting"] == []


@pytest.mark.django_db
def test_build_models_snapshot_with_waiting(chatter, content_model, fan):
    """A conversation awaiting reply shows up in waiting list."""
    conv = Conversation.objects.create(fan=fan, content_model=content_model, chatter=chatter)
    create_message(conversation_id=conv.id, sender=Message.SENDER_FAN, text="hello")

    result = build_models_snapshot()
    entry = next(r for r in result if r["id"] == content_model.id)
    assert entry["dialogs_count"] == 1
    assert len(entry["waiting"]) == 1
    w = entry["waiting"][0]
    assert w["conversation_id"] == conv.id
    assert w["fan_name"] == fan.name
    assert w["waiting_since"] is not None


@pytest.mark.django_db
def test_build_models_snapshot_aggregates_across_chatters(chatter, chatter2, content_model, fan, fan2):
    """dialogs_count and waiting aggregate across all chatters for a single model."""
    conv1 = Conversation.objects.create(fan=fan, content_model=content_model, chatter=chatter)
    conv2 = Conversation.objects.create(fan=fan2, content_model=content_model, chatter=chatter2)
    # fan sends to both conversations
    create_message(conversation_id=conv1.id, sender=Message.SENDER_FAN, text="hi from fan1")
    create_message(conversation_id=conv2.id, sender=Message.SENDER_FAN, text="hi from fan2")

    result = build_models_snapshot()
    entry = next(r for r in result if r["id"] == content_model.id)
    assert entry["dialogs_count"] == 2
    assert len(entry["waiting"]) == 2


@pytest.mark.django_db
def test_build_models_snapshot_no_waiting_when_chatter_replied(chatter, content_model, fan):
    """After chatter replies, conversation is no longer in waiting."""
    conv = Conversation.objects.create(fan=fan, content_model=content_model, chatter=chatter)
    create_message(conversation_id=conv.id, sender=Message.SENDER_FAN, text="hello")
    create_message(conversation_id=conv.id, sender=Message.SENDER_CHATTER, text="hi back")

    result = build_models_snapshot()
    entry = next(r for r in result if r["id"] == content_model.id)
    assert entry["dialogs_count"] == 1
    assert entry["waiting"] == []


@pytest.mark.django_db
def test_build_models_snapshot_ordered_by_id(db):
    """Models are returned ordered by id."""
    m1 = ContentModel.objects.create(name="Alpha", avatar="A")
    m2 = ContentModel.objects.create(name="Beta", avatar="B")
    result = build_models_snapshot()
    ids = [r["id"] for r in result]
    assert ids == sorted(ids)
    assert m1.id in ids and m2.id in ids


# --- Snapshot endpoint models key tests ---


@pytest.mark.django_db
def test_snapshot_response_includes_models_key(client, teamlead, content_model):
    """GET /api/monitor/snapshot/ response includes models list."""
    client.force_login(teamlead)
    response = client.get("/api/monitor/snapshot/")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert isinstance(data["models"], list)
    entry = next((m for m in data["models"] if m["id"] == content_model.id), None)
    assert entry is not None
    assert "name" in entry
    assert "avatar" in entry
    assert "dialogs_count" in entry
    assert "waiting" in entry


@pytest.mark.django_db
def test_snapshot_models_listed_even_with_no_waiting(client, teamlead, chatter, conversation):
    """A content model with no waiting dialogs still appears in models list."""
    # conversation has no fan message → no waiting
    client.force_login(teamlead)
    response = client.get("/api/monitor/snapshot/")
    data = response.json()
    models = data["models"]
    # The content_model from the conversation fixture must be present
    conv_obj = conversation
    model_ids = [m["id"] for m in models]
    assert conv_obj.content_model_id in model_ids
    matched = next(m for m in models if m["id"] == conv_obj.content_model_id)
    assert matched["dialogs_count"] == 1
    assert matched["waiting"] == []
