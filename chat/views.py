import random

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsChatter
from chat.models import Conversation, Message
from chat.serializers import ConversationSerializer, MessageSerializer
from chat.services import create_message, schedule_message_broadcast


FAN_PHRASES = [
    "Hey, are you there?",
    "I miss you 😘",
    "What are you doing tonight?",
    "Can we chat?",
    "You're amazing!",
    "I love your content ❤️",
    "When's the next post?",
    "You're so beautiful!",
    "I just subscribed!",
    "Can I get a shoutout?",
]


class ConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "overdue_seconds": settings.OVERDUE_SECONDS,
                "presence_grace_seconds": settings.PRESENCE_GRACE_SECONDS,
                "heartbeat_seconds": settings.HEARTBEAT_SECONDS,
            }
        )


class ConversationListView(APIView):
    permission_classes = [IsChatter]

    def get(self, request):
        convs = (
            Conversation.objects.filter(chatter=request.user)
            .select_related("fan", "content_model")
            .prefetch_related("messages")
            .order_by("-last_message_at")
        )
        return Response(ConversationSerializer(convs, many=True).data)


class MessageListView(APIView):
    permission_classes = [IsChatter]

    def get(self, request, conversation_id):
        try:
            conv = Conversation.objects.get(id=conversation_id, chatter=request.user)
        except Conversation.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        page_size = min(int(request.query_params.get("limit", settings.MESSAGES_PAGE_SIZE)), 100)
        before_id = request.query_params.get("before_id")

        qs = conv.messages.order_by("-id")
        if before_id:
            qs = qs.filter(id__lt=int(before_id))

        msgs = list(qs[: page_size + 1])
        has_more = len(msgs) > page_size
        return Response(
            {
                "results": MessageSerializer(msgs[:page_size], many=True).data,
                "has_more": has_more,
            }
        )


class MarkReadView(APIView):
    permission_classes = [IsChatter]

    def post(self, request, conversation_id):
        with transaction.atomic():
            try:
                conv = Conversation.objects.select_for_update().get(
                    id=conversation_id, chatter=request.user
                )
            except Conversation.DoesNotExist:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

            conv.unread_count = 0
            conv.save(update_fields=["unread_count"])
            chatter_id = conv.chatter_id
            conv_id = conv.id

            def send_read():
                channel_layer = get_channel_layer()
                if channel_layer is None:
                    return
                try:
                    async_to_sync(channel_layer.group_send)(
                        f"chatter.{chatter_id}",
                        {
                            "type": "chat.conversation_read",
                            "payload": {"conversation_id": conv_id},
                        },
                    )
                except Exception:
                    pass

            transaction.on_commit(send_read)

        return Response({"conversation_id": conv.id, "unread_count": 0})


class SyncView(APIView):
    permission_classes = [IsChatter]

    def get(self, request):
        after_id = request.query_params.get("after_id", 0)
        try:
            after_id = int(after_id)
        except (ValueError, TypeError):
            after_id = 0

        convs = Conversation.objects.filter(chatter=request.user).select_related("fan", "content_model")
        conv_ids = [c.id for c in convs]

        messages = (
            Message.objects.filter(conversation_id__in=conv_ids, id__gt=after_id)
            .order_by("id")[:500]
        )

        return Response(
            {
                "messages": MessageSerializer(messages, many=True).data,
                "conversations": ConversationSerializer(convs, many=True).data,
            }
        )


class FanMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conversation_id = request.data.get("conversation_id")
        text = request.data.get("text")

        if conversation_id:
            try:
                conv = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            conv = Conversation.objects.order_by("?").first()
            if conv is None:
                return Response({"detail": "No conversations exist."}, status=status.HTTP_404_NOT_FOUND)

        if not text:
            text = random.choice(FAN_PHRASES)

        msg = create_message(
            conversation_id=conv.id,
            sender=Message.SENDER_FAN,
            text=text,
        )
        schedule_message_broadcast(msg.id, conv.id)

        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)
