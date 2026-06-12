from django.urls import path

from chat.views import (
    ConfigView,
    ConversationListView,
    FanMessageView,
    MarkReadView,
    MessageListView,
    SyncView,
)

urlpatterns = [
    path("config/", ConfigView.as_view(), name="config"),
    path("conversations/", ConversationListView.as_view(), name="conversation-list"),
    path("conversations/<int:conversation_id>/messages/", MessageListView.as_view(), name="message-list"),
    path("conversations/<int:conversation_id>/read/", MarkReadView.as_view(), name="conversation-read"),
    path("sync/", SyncView.as_view(), name="sync"),
    path("demo/fan-message/", FanMessageView.as_view(), name="fan-message"),
]
