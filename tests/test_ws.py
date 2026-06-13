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
    connected, _ = await communicator.connect()
    assert connected

    response = await communicator.receive_output(timeout=5)
    assert response["type"] == "websocket.close"
    assert response.get("code") == 4401
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

    cid = str(uuid.uuid4())
    await communicator.send_json_to(
        {
            "type": "message.send",
            "payload": {
                "conversation_id": conversation.id,
                "text": "   ",
                "kind": "text",
                "client_msg_id": cid,
            },
        }
    )

    response = await communicator.receive_json_from(timeout=5)
    assert response["type"] == "error"
    assert response["payload"]["code"] == "empty_text"
    assert str(response["payload"]["client_msg_id"]) == cid

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

    cid = str(uuid.uuid4())
    await communicator.send_json_to(
        {
            "type": "message.send",
            "payload": {
                "conversation_id": conversation2.id,
                "text": "Trying to intrude",
                "kind": "text",
                "client_msg_id": cid,
            },
        }
    )

    response = await communicator.receive_json_from(timeout=5)
    assert response["type"] == "error"
    assert str(response["payload"]["client_msg_id"]) == cid

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

    cid = str(uuid.uuid4())
    await communicator.send_json_to(
        {
            "type": "message.send",
            "payload": {
                "conversation_id": conversation.id,
                "text": "My PPV content",
                "kind": "ppv",
                "client_msg_id": cid,
            },
        }
    )

    response = await communicator.receive_json_from(timeout=5)
    assert response["type"] == "error"
    assert "ppv_price" in response["payload"]["code"]
    assert str(response["payload"]["client_msg_id"]) == cid

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_message_send_triggers_monitor_update(chatter, teamlead, conversation):
    """When chatter sends a message, teamlead receives monitor.update."""
    chatter_session = await _async_make_session(chatter)
    teamlead_session = await _async_make_session(teamlead)

    chatter_comm = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={chatter_session}".encode())],
    )
    teamlead_comm = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={teamlead_session}".encode())],
    )

    # teamlead subscribes to "monitor" group first so it receives all subsequent events
    teamlead_connected, _ = await teamlead_comm.connect()
    assert teamlead_connected

    # chatter connects — triggers _push_monitor_update to "monitor" group
    chatter_connected, _ = await chatter_comm.connect()
    assert chatter_connected

    # teamlead receives the monitor.update emitted when chatter joined
    initial = await teamlead_comm.receive_json_from(timeout=5)
    assert initial["type"] == "monitor.update"

    await chatter_comm.send_json_to(
        {
            "type": "message.send",
            "payload": {
                "conversation_id": conversation.id,
                "text": "Hello from chatter!",
                "kind": "text",
            },
        }
    )

    # chatter receives its own message.new
    chatter_msg = await chatter_comm.receive_json_from(timeout=5)
    assert chatter_msg["type"] == "message.new"

    # teamlead receives monitor.update with updated chatter snapshot
    monitor_msg = await teamlead_comm.receive_json_from(timeout=5)
    assert monitor_msg["type"] == "monitor.update"
    assert monitor_msg["payload"]["chatter"]["id"] == chatter.id
    assert "models" in monitor_msg["payload"]

    await chatter_comm.disconnect()
    await teamlead_comm.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_ping_sends_presence_update_to_monitor(chatter, teamlead):
    """Chatter ping causes presence.update with chatter_id and last_seen in monitor group."""
    teamlead_session = await _async_make_session(teamlead)
    chatter_session = await _async_make_session(chatter)

    teamlead_comm = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={teamlead_session}".encode())],
    )
    chatter_comm = WebsocketCommunicator(
        application,
        "/ws/",
        headers=[(b"cookie", f"sessionid={chatter_session}".encode())],
    )

    teamlead_connected, _ = await teamlead_comm.connect()
    assert teamlead_connected

    chatter_connected, _ = await chatter_comm.connect()
    assert chatter_connected

    # Drain the monitor.update emitted on chatter connect
    initial = await teamlead_comm.receive_json_from(timeout=5)
    assert initial["type"] == "monitor.update"

    await chatter_comm.send_json_to({"type": "ping", "payload": {}})

    pong = await chatter_comm.receive_json_from(timeout=5)
    assert pong["type"] == "pong"

    presence_event = await teamlead_comm.receive_json_from(timeout=5)
    assert presence_event["type"] == "presence.update"
    assert presence_event["payload"]["chatter_id"] == chatter.id
    assert presence_event["payload"]["last_seen"] is not None

    await chatter_comm.disconnect()
    await teamlead_comm.disconnect()


from asgiref.sync import sync_to_async


async def _async_make_session(user):
    return await sync_to_async(make_session_for_user)(user)
