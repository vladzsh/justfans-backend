import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from chat.models import ContentModel, Conversation, Message
from chat.serializers import ConversationSerializer, MessageSerializer

logger = logging.getLogger(__name__)


def build_models_snapshot():
    """Build the full models aggregation for the monitor: all ContentModels ordered by id."""
    models = ContentModel.objects.order_by("id")
    result = []
    for model in models:
        dialogs_count = Conversation.objects.filter(content_model=model).count()
        waiting = list(
            Conversation.objects.filter(
                content_model=model,
                awaiting_reply_since__isnull=False,
            ).values("id", "awaiting_reply_since", "fan__name")
        )
        result.append(
            {
                "id": model.id,
                "name": model.name,
                "avatar": model.avatar,
                "dialogs_count": dialogs_count,
                "waiting": [
                    {
                        "conversation_id": w["id"],
                        "fan_name": w["fan__name"],
                        "waiting_since": (
                            w["awaiting_reply_since"].isoformat()
                            if w["awaiting_reply_since"]
                            else None
                        ),
                    }
                    for w in waiting
                ],
            }
        )
    return result


def build_chatter_snapshot(chatter_id):
    """Build monitor.update payload for a single chatter by id."""
    from chat.presence import get_presence_data
    from accounts.models import User

    chatter = User.objects.get(id=chatter_id)
    waiting = list(
        Conversation.objects.filter(
            chatter=chatter,
            awaiting_reply_since__isnull=False,
        ).values("id", "awaiting_reply_since", "fan__name")
    )
    all_conversations = list(
        Conversation.objects.filter(chatter=chatter).values(
            "id",
            "fan__name",
            "awaiting_reply_since",
            "content_model__id",
            "content_model__name",
            "content_model__avatar",
        )
    )
    presence = get_presence_data(chatter.id)
    dialogs_count = Conversation.objects.filter(chatter=chatter).count()

    return {
        "id": chatter.id,
        "display_name": chatter.display_name or chatter.username,
        "connected": presence["connected"],
        "last_seen": presence["last_seen"],
        "dialogs_count": dialogs_count,
        "waiting": [
            {
                "conversation_id": w["id"],
                "fan_name": w["fan__name"],
                "waiting_since": w["awaiting_reply_since"].isoformat() if w["awaiting_reply_since"] else None,
            }
            for w in waiting
        ],
        "dialogs": [
            {
                "conversation_id": d["id"],
                "fan_name": d["fan__name"],
                "awaiting_reply_since": (
                    d["awaiting_reply_since"].isoformat()
                    if d["awaiting_reply_since"]
                    else None
                ),
                "model_id": d["content_model__id"],
                "model_name": d["content_model__name"],
                "model_avatar": d["content_model__avatar"],
            }
            for d in all_conversations
        ],
    }


def create_message(*, conversation_id, sender, text, kind="text", ppv_price=None, client_msg_id=None):
    """
    Create a message (or return existing if client_msg_id duplicates).

    Updates conversation state atomically. Does NOT broadcast — callers
    are responsible for sending WS events (see broadcast_message_new).
    """
    with transaction.atomic():
        try:
            conv = Conversation.objects.select_for_update().get(id=conversation_id)
        except Conversation.DoesNotExist:
            raise ValueError(f"Conversation {conversation_id} not found")

        if client_msg_id is not None:
            existing = Message.objects.filter(
                conversation=conv,
                client_msg_id=client_msg_id,
            ).first()
            if existing is not None:
                return existing

        now = timezone.now()

        msg = Message.objects.create(
            conversation=conv,
            sender=sender,
            text=text,
            kind=kind,
            ppv_price=ppv_price,
            client_msg_id=client_msg_id,
            created_at=now,
        )

        conv.last_message_at = now

        if sender == Message.SENDER_FAN:
            conv.unread_count += 1
            if conv.awaiting_reply_since is None:
                conv.awaiting_reply_since = now
        else:
            conv.awaiting_reply_since = None

        conv.save(update_fields=["last_message_at", "unread_count", "awaiting_reply_since"])

    return msg


def broadcast_message_new_sync(msg_id, conv_id):
    """
    Broadcast message.new + monitor.update after commit.
    Called via transaction.on_commit from sync (REST) context.
    """
    try:
        msg = Message.objects.get(id=msg_id)
        conv = Conversation.objects.select_related("fan", "content_model", "chatter").get(id=conv_id)
    except Exception as e:
        logger.exception("Error in broadcast_message_new_sync for msg_id=%s conv_id=%s: %s", msg_id, conv_id, e)
        return

    msg_data = MessageSerializer(msg).data
    conv_data = ConversationSerializer(conv).data
    chatter_id = conv.chatter_id
    chatter_snapshot = build_chatter_snapshot(chatter_id)
    models_snapshot = build_models_snapshot()

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"chatter.{chatter_id}",
            {
                "type": "chat.message_new",
                "payload": {"message": msg_data, "conversation": conv_data},
            },
        )
        async_to_sync(channel_layer.group_send)(
            "monitor",
            {
                "type": "chat.monitor_update",
                "payload": {"chatter": chatter_snapshot, "models": models_snapshot},
            },
        )
    except Exception as e:
        logger.exception("Error sending channel messages for msg_id=%s conv_id=%s: %s", msg_id, conv_id, e)
        pass


def schedule_message_broadcast(msg_id, conv_id):
    """Register on_commit broadcast for REST/sync callers."""
    transaction.on_commit(lambda: broadcast_message_new_sync(msg_id, conv_id))
