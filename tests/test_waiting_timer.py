"""Task 4.2: Tests for awaiting_reply_since logic and unread_count."""
import pytest

from chat.models import Conversation, Message
from chat.services import create_message


@pytest.mark.django_db(transaction=True)
def test_fan_message_sets_awaiting_reply_since(conversation):
    assert conversation.awaiting_reply_since is None

    create_message(
        conversation_id=conversation.id,
        sender=Message.SENDER_FAN,
        text="Hey!",
    )

    conversation.refresh_from_db()
    assert conversation.awaiting_reply_since is not None


@pytest.mark.django_db(transaction=True)
def test_fan_message_increments_unread(conversation):
    create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Hi")
    conversation.refresh_from_db()
    assert conversation.unread_count == 1

    create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Still there?")
    conversation.refresh_from_db()
    assert conversation.unread_count == 2


@pytest.mark.django_db(transaction=True)
def test_second_fan_message_does_not_reset_awaiting(conversation):
    create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="First")
    conversation.refresh_from_db()
    first_since = conversation.awaiting_reply_since
    assert first_since is not None

    create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Second")
    conversation.refresh_from_db()
    assert conversation.awaiting_reply_since == first_since


@pytest.mark.django_db(transaction=True)
def test_chatter_reply_clears_awaiting(conversation):
    create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Hey")
    conversation.refresh_from_db()
    assert conversation.awaiting_reply_since is not None

    create_message(
        conversation_id=conversation.id,
        sender=Message.SENDER_CHATTER,
        text="Here I am!",
    )
    conversation.refresh_from_db()
    assert conversation.awaiting_reply_since is None


@pytest.mark.django_db(transaction=True)
def test_mark_read_resets_unread(client, chatter, conversation):
    create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Hi")
    create_message(conversation_id=conversation.id, sender=Message.SENDER_FAN, text="Hello")
    conversation.refresh_from_db()
    assert conversation.unread_count == 2

    client.force_login(chatter)
    resp = client.post(f"/api/conversations/{conversation.id}/read/")
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 0

    conversation.refresh_from_db()
    assert conversation.unread_count == 0
