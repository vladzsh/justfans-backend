"""Task 4.4: Idempotency tests and on_commit gating."""
import uuid

import pytest

from chat.models import Message
from chat.services import create_message, schedule_message_broadcast


@pytest.mark.django_db(transaction=True)
def test_duplicate_client_msg_id_no_new_message(conversation):
    cid = uuid.uuid4()

    msg1 = create_message(
        conversation_id=conversation.id,
        sender=Message.SENDER_CHATTER,
        text="Hello",
        client_msg_id=cid,
    )

    msg2 = create_message(
        conversation_id=conversation.id,
        sender=Message.SENDER_CHATTER,
        text="Hello again",
        client_msg_id=cid,
    )

    assert msg1.id == msg2.id
    count = Message.objects.filter(conversation=conversation).count()
    assert count == 1


@pytest.mark.django_db(transaction=True)
def test_duplicate_client_msg_id_returns_existing(conversation):
    cid = uuid.uuid4()
    msg1 = create_message(
        conversation_id=conversation.id,
        sender=Message.SENDER_CHATTER,
        text="Original",
        client_msg_id=cid,
    )

    msg2 = create_message(
        conversation_id=conversation.id,
        sender=Message.SENDER_CHATTER,
        text="Duplicate",
        client_msg_id=cid,
    )

    assert msg2.text == "Original"


@pytest.mark.django_db(transaction=True)
def test_broadcast_not_called_on_rollback(conversation, monkeypatch):
    """schedule_message_broadcast's on_commit callback does not fire when the wrapping
    transaction is rolled back."""
    from django.db import transaction

    broadcast_calls = []
    monkeypatch.setattr(
        "chat.services.broadcast_message_new_sync",
        lambda msg_id, conv_id: broadcast_calls.append((msg_id, conv_id)),
    )

    try:
        with transaction.atomic():
            msg = create_message(
                conversation_id=conversation.id,
                sender=Message.SENDER_FAN,
                text="will rollback",
            )
            schedule_message_broadcast(msg.id, conversation.id)
            raise Exception("forced rollback")
    except Exception:
        pass

    assert broadcast_calls == [], "broadcast fired despite rollback"
    assert Message.objects.filter(conversation=conversation, text="will rollback").count() == 0


@pytest.mark.django_db
def test_null_client_msg_id_allows_multiple_messages(conversation):
    """Messages without client_msg_id are not deduplicated."""
    m1 = create_message(
        conversation_id=conversation.id,
        sender=Message.SENDER_CHATTER,
        text="Same text",
    )
    m2 = create_message(
        conversation_id=conversation.id,
        sender=Message.SENDER_CHATTER,
        text="Same text",
    )
    assert m1.id != m2.id
    assert Message.objects.filter(conversation=conversation).count() == 2
