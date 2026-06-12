"""Task 4.4: Idempotency tests and on_commit gating."""
import uuid

import pytest
from pytest_django.fixtures import django_capture_on_commit_callbacks

from chat.models import Message
from chat.services import create_message


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


@pytest.mark.django_db
def test_on_commit_not_called_on_rollback(conversation):
    """Events must not fire when transaction rolls back."""
    callbacks = []

    from django.db import transaction

    def boom():
        with transaction.atomic():
            from chat.models import Message as M
            M.objects.create(
                conversation=conversation,
                sender="fan",
                text="will rollback",
                kind="text",
            )
            transaction.on_commit(lambda: callbacks.append("fired"))
            raise Exception("forced rollback")

    try:
        boom()
    except Exception:
        pass

    assert callbacks == [], "on_commit fired despite rollback"
    assert Message.objects.filter(conversation=conversation).count() == 0


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
