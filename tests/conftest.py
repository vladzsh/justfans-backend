import pytest

from accounts.models import User
from chat.models import ContentModel, Conversation, Fan, Message


@pytest.fixture
def chatter(db):
    return User.objects.create_user(
        username="chatter1",
        password="testpass",
        role="chatter",
        display_name="Chatter One",
    )


@pytest.fixture
def chatter2(db):
    return User.objects.create_user(
        username="chatter2",
        password="testpass",
        role="chatter",
        display_name="Chatter Two",
    )


@pytest.fixture
def teamlead(db):
    return User.objects.create_user(
        username="teamlead1",
        password="testpass",
        role="teamlead",
        display_name="Team Lead",
    )


@pytest.fixture
def fan(db):
    return Fan.objects.create(name="TestFan", avatar="🧔")


@pytest.fixture
def fan2(db):
    return Fan.objects.create(name="TestFan2", avatar="👤")


@pytest.fixture
def content_model(db):
    return ContentModel.objects.create(name="Stella", avatar="💃")


@pytest.fixture
def conversation(db, chatter, fan, content_model):
    return Conversation.objects.create(
        fan=fan,
        content_model=content_model,
        chatter=chatter,
    )


@pytest.fixture
def conversation2(db, chatter2, fan2, content_model):
    return Conversation.objects.create(
        fan=fan2,
        content_model=content_model,
        chatter=chatter2,
    )
