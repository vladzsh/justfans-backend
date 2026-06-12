"""Auth boundary tests: 401 for anonymous, 403 for wrong role."""
import pytest


@pytest.mark.django_db
def test_anonymous_get_conversations_returns_401(client):
    response = client.get("/api/conversations/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_anonymous_get_messages_returns_401(client, conversation):
    response = client.get(f"/api/conversations/{conversation.id}/messages/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_anonymous_config_returns_401(client):
    response = client.get("/api/config/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_anonymous_monitor_snapshot_returns_401(client):
    response = client.get("/api/monitor/snapshot/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_teamlead_get_conversations_returns_403(client, teamlead):
    client.force_login(teamlead)
    response = client.get("/api/conversations/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_chatter_monitor_snapshot_returns_403(client, chatter):
    client.force_login(chatter)
    response = client.get("/api/monitor/snapshot/")
    assert response.status_code == 403
