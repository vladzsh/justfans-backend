"""Task 4.5: WebSocket flow tests via channels WebsocketCommunicator."""
import json
import uuid

import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY

from config.asgi import application
from chat.models import Message


def make_session_for_user(user):
    """Create a real Django session for a user and return session key."""
    session = SessionStore()
    session[SESSION_KEY] = str(user.pk)
    session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    session[HASH_SESSION_KEY] = user.get_session_auth_hash()
    session.save()
    return session.session_key


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_rejects_unauthenticated():
    communicator = WebsocketCommunicator(application, "/ws/")
    connected, code = await communicator.connect()
    assert not connected
    assert code == 4401
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_chatter_connects(chatter):
    session_key = await _async_make_session(chatter)
    communicator = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={session_key}".encode())],
    )
    connected, _ = await communicator.connect()
    assert connected
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_ping_pong(chatter):
    session_key = await _async_make_session(chatter)
    communicator = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={session_key}".encode())],
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({"type": "ping", "payload": {}})
    response = await communicator.receive_json_from(timeout=5)
    assert response["type"] == "pong"

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_message_send_triggers_message_new(chatter, conversation):
    session_key = await _async_make_session(chatter)
    communicator = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={session_key}".encode())],
    )
    connected, _ = await communicator.connect()
    assert connected

    cid = str(uuid.uuid4())
    await communicator.send_json_to(
        {
            "type": "message.send",
            "payload": {
                "conversation_id": conversation.id,
                "text": "Hello from chatter",
                "kind": "text",
                "client_msg_id": cid,
            },
        }
    )

    response = await communicator.receive_json_from(timeout=5)
    assert response["type"] == "message.new"
    assert response["payload"]["message"]["text"] == "Hello from chatter"
    assert response["payload"]["message"]["sender"] == "chatter"
    assert str(response["payload"]["message"]["client_msg_id"]) == cid

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_empty_text_returns_error(chatter, conversation):
    session_key = await _async_make_session(chatter)
    communicator = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={session_key}".encode())],
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to(
        {
            "type": "message.send",
            "payload": {
                "conversation_id": conversation.id,
                "text": "   ",
                "kind": "text",
                "client_msg_id": str(uuid.uuid4()),
            },
        }
    )

    response = await communicator.receive_json_from(timeout=5)
    assert response["type"] == "error"
    assert response["payload"]["code"] == "empty_text"

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_foreign_conversation_returns_error(chatter, conversation2):
    """Chatter cannot send to a conversation belonging to chatter2."""
    session_key = await _async_make_session(chatter)
    communicator = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={session_key}".encode())],
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to(
        {
            "type": "message.send",
            "payload": {
                "conversation_id": conversation2.id,
                "text": "Trying to intrude",
                "kind": "text",
                "client_msg_id": str(uuid.uuid4()),
            },
        }
    )

    response = await communicator.receive_json_from(timeout=5)
    assert response["type"] == "error"

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_ppv_without_price_returns_error(chatter, conversation):
    session_key = await _async_make_session(chatter)
    communicator = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={session_key}".encode())],
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to(
        {
            "type": "message.send",
            "payload": {
                "conversation_id": conversation.id,
                "text": "My PPV content",
                "kind": "ppv",
                "client_msg_id": str(uuid.uuid4()),
            },
        }
    )

    response = await communicator.receive_json_from(timeout=5)
    assert response["type"] == "error"
    assert "ppv_price" in response["payload"]["code"]

    await communicator.disconnect()


from asgiref.sync import sync_to_async


async def _async_make_session(user):
    return await sync_to_async(make_session_for_user)(user)
