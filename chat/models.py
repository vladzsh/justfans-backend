from django.conf import settings
from django.db import models


class ContentModel(models.Model):
    name = models.CharField(max_length=255)
    avatar = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class Fan(models.Model):
    name = models.CharField(max_length=255)
    avatar = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class Conversation(models.Model):
    fan = models.ForeignKey(Fan, on_delete=models.CASCADE, related_name="conversations")
    content_model = models.ForeignKey(ContentModel, on_delete=models.CASCADE, related_name="conversations")
    chatter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    unread_count = models.IntegerField(default=0)
    awaiting_reply_since = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("fan", "content_model")]

    def __str__(self):
        return f"Conversation({self.fan} / {self.content_model})"


class Message(models.Model):
    SENDER_FAN = "fan"
    SENDER_CHATTER = "chatter"
    SENDER_CHOICES = [
        (SENDER_FAN, "Fan"),
        (SENDER_CHATTER, "Chatter"),
    ]
    KIND_TEXT = "text"
    KIND_PPV = "ppv"
    KIND_CHOICES = [
        (KIND_TEXT, "Text"),
        (KIND_PPV, "PPV"),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    text = models.TextField()
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_TEXT)
    ppv_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    client_msg_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["conversation", "id"], name="message_conv_id_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "client_msg_id"],
                condition=models.Q(client_msg_id__isnull=False),
                name="unique_conversation_client_msg_id",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(kind="text", ppv_price__isnull=True)
                    | models.Q(kind="ppv", ppv_price__isnull=False, ppv_price__gt=0)
                ),
                name="ppv_price_check",
            ),
        ]

    def __str__(self):
        return f"Message({self.id}, {self.sender}, {self.kind})"
