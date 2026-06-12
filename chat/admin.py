from django.contrib import admin

from chat.models import ContentModel, Conversation, Fan, Message


@admin.register(ContentModel)
class ContentModelAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "avatar"]


@admin.register(Fan)
class FanAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "avatar"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "fan", "content_model", "chatter", "unread_count", "awaiting_reply_since"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "sender", "kind", "created_at"]
