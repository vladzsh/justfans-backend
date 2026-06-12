import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework.utils.encoders import JSONEncoder

from chat.models import Conversation, Message
from chat.presence import delete_presence, set_presence
from chat.services import build_chatter_snapshot, create_message
from chat.serializers import ConversationSerializer, MessageSerializer


def _dumps(obj):
    return json.dumps(obj, cls=JSONEncoder)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user = user
        self.group_name = None

        if user.role == "chatter":
            self.group_name = f"chatter.{user.id}"
        elif user.role == "teamlead":
            self.group_name = "monitor"
        else:
            await self.close(code=4401)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        if user.role == "chatter":
            await sync_to_async(set_presence)(user.id)
            await self._push_monitor_update(user.id)

    async def disconnect(self, close_code):
        if not hasattr(self, "user"):
            return

        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        if self.user.role == "chatter":
            await sync_to_async(delete_presence)(self.user.id)
            await self._push_monitor_update(self.user.id)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        msg_type = data.get("type")
        payload = data.get("payload", {})

        if msg_type == "ping":
            if self.user.role == "chatter":
                await sync_to_async(set_presence)(self.user.id)
            await self.send(text_data=json.dumps({"type": "pong", "payload": {}}))

        elif msg_type == "message.send":
            await self._handle_message_send(payload)

    async def _handle_message_send(self, payload):
        conversation_id = payload.get("conversation_id")
        text = payload.get("text", "")
        kind = payload.get("kind", "text")
        ppv_price = payload.get("ppv_price")
        client_msg_id = payload.get("client_msg_id")

        if not text or not str(text).strip():
            await self._send_error("empty_text", "Text must not be empty.")
            return

        if kind == "ppv":
            if ppv_price is None:
                await self._send_error("ppv_price_required", "ppv_price is required for PPV messages.")
                return
            try:
                ppv_price = float(ppv_price)
                if ppv_price <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                await self._send_error("ppv_price_invalid", "ppv_price must be positive.")
                return
        elif kind == "text" and ppv_price is not None:
            await self._send_error("ppv_price_forbidden", "ppv_price not allowed for text messages.")
            return

        owned = await sync_to_async(
            Conversation.objects.filter(id=conversation_id, chatter=self.user).exists
        )()
        if not owned:
            await self._send_error("forbidden", "Conversation not found or not yours.")
            return

        try:
            msg = await sync_to_async(create_message)(
                conversation_id=conversation_id,
                sender=Message.SENDER_CHATTER,
                text=text,
                kind=kind,
                ppv_price=ppv_price,
                client_msg_id=client_msg_id,
            )
        except Exception as e:
            await self._send_error("internal_error", str(e))
            return

        def _serialize_message_and_conv():
            conv = Conversation.objects.select_related("fan", "content_model").get(id=conversation_id)
            return (
                json.loads(_dumps(MessageSerializer(msg).data)),
                json.loads(_dumps(ConversationSerializer(conv).data)),
            )

        msg_json, conv_json = await sync_to_async(_serialize_message_and_conv)()

        await self.channel_layer.group_send(
            f"chatter.{self.user.id}",
            {
                "type": "chat.message_new",
                "payload": {"message": msg_json, "conversation": conv_json},
            },
        )

        monitor_payload = await sync_to_async(build_chatter_snapshot)(self.user.id)
        await self.channel_layer.group_send(
            "monitor",
            {"type": "chat.monitor_update", "payload": monitor_payload},
        )

    async def _send_error(self, code, detail):
        await self.send(text_data=json.dumps({"type": "error", "payload": {"code": code, "detail": detail}}))

    async def _push_monitor_update(self, chatter_id):
        try:
            snapshot = await sync_to_async(build_chatter_snapshot)(chatter_id)
            await self.channel_layer.group_send(
                "monitor",
                {"type": "chat.monitor_update", "payload": snapshot},
            )
        except Exception:
            pass

    # Channel layer event handlers — payloads are already JSON-safe dicts

    async def chat_message_new(self, event):
        await self.send(text_data=json.dumps({"type": "message.new", "payload": event["payload"]}))

    async def chat_conversation_read(self, event):
        await self.send(text_data=json.dumps({"type": "conversation.read", "payload": event["payload"]}))

    async def chat_monitor_update(self, event):
        await self.send(text_data=json.dumps({"type": "monitor.update", "payload": event["payload"]}))
