from rest_framework import serializers

from chat.models import Conversation, Fan, ContentModel, Message


class FanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fan
        fields = ["id", "name", "avatar"]


class ContentModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentModel
        fields = ["id", "name", "avatar"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "conversation_id",
            "sender",
            "kind",
            "text",
            "ppv_price",
            "client_msg_id",
            "created_at",
        ]


class LastMessageSerializer(serializers.Serializer):
    text = serializers.CharField()
    sender = serializers.CharField()
    created_at = serializers.DateTimeField()


class ConversationSerializer(serializers.ModelSerializer):
    fan = FanSerializer(read_only=True)
    model = ContentModelSerializer(source="content_model", read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "fan",
            "model",
            "last_message",
            "last_message_at",
            "unread_count",
            "awaiting_reply_since",
        ]

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-id").first()
        if msg is None:
            return None
        return {
            "text": msg.text,
            "sender": msg.sender,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
