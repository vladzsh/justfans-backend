from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from chat.models import ContentModel, Conversation, Fan, Message

DEMO_PASSWORD = "demo1234"

CONTENT_MODELS_DATA = [
    {"name": "Stella", "avatar": "💃"},
    {"name": "Luna", "avatar": "🌙"},
    {"name": "Aria", "avatar": "🎵"},
]

FANS_DATA = [
    {"name": "Mike", "avatar": "🧔"},
    {"name": "Jake", "avatar": "👨"},
    {"name": "Tom", "avatar": "🕵️"},
    {"name": "Sam", "avatar": "🙋"},
    {"name": "Alex", "avatar": "👤"},
    {"name": "Chris", "avatar": "🧑"},
    {"name": "Ryan", "avatar": "😎"},
    {"name": "Leo", "avatar": "🦁"},
]

CHATTERS_DATA = [
    {"username": "chatter1", "display_name": "Alice"},
    {"username": "chatter2", "display_name": "Bob"},
    {"username": "chatter3", "display_name": "Carol"},
    {"username": "chatter4", "display_name": "Dave"},
]

TEAMLEAD_DATA = {"username": "teamlead1", "display_name": "Team Lead"}


class Command(BaseCommand):
    help = "Seed the database with demo data (idempotent)"

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        content_models = []
        for data in CONTENT_MODELS_DATA:
            obj, _ = ContentModel.objects.get_or_create(name=data["name"], defaults={"avatar": data["avatar"]})
            content_models.append(obj)

        fans = []
        for data in FANS_DATA:
            obj, _ = Fan.objects.get_or_create(name=data["name"], defaults={"avatar": data["avatar"]})
            fans.append(obj)

        chatters = []
        for data in CHATTERS_DATA:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={
                    "role": "chatter",
                    "display_name": data["display_name"],
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            chatters.append(user)

        teamlead, created = User.objects.get_or_create(
            username=TEAMLEAD_DATA["username"],
            defaults={
                "role": "teamlead",
                "display_name": TEAMLEAD_DATA["display_name"],
            },
        )
        if created:
            teamlead.set_password(DEMO_PASSWORD)
            teamlead.save()

        # Create conversations: each chatter gets 2 conversations with different fans
        now = timezone.now()
        conversations_data = [
            # chatter1 conversations
            (chatters[0], fans[0], content_models[0], True),   # awaiting
            (chatters[0], fans[1], content_models[1], False),
            # chatter2 conversations
            (chatters[1], fans[2], content_models[0], True),   # awaiting
            (chatters[1], fans[3], content_models[2], False),
            # chatter3 conversations
            (chatters[2], fans[4], content_models[1], True),   # awaiting
            (chatters[2], fans[5], content_models[2], False),
            # chatter4 conversations
            (chatters[3], fans[6], content_models[0], False),
            (chatters[3], fans[7], content_models[1], False),
        ]

        for chatter, fan, model, awaiting in conversations_data:
            conv, created = Conversation.objects.get_or_create(
                fan=fan,
                content_model=model,
                defaults={
                    "chatter": chatter,
                    "last_message_at": now,
                },
            )

            if not created:
                continue

            # Seed conversation history
            m1 = Message.objects.create(
                conversation=conv,
                sender="fan",
                text=f"Hey {model.name}, how are you?",
                kind="text",
            )

            m2 = Message.objects.create(
                conversation=conv,
                sender="chatter",
                text="Hey! I'm doing great, thanks for reaching out! 😊",
                kind="text",
            )

            # PPV message from chatter
            m3 = Message.objects.create(
                conversation=conv,
                sender="chatter",
                text="Check out my exclusive content!",
                kind="ppv",
                ppv_price="9.99",
            )

            if awaiting:
                # Fan's unanswered message — sets awaiting_reply_since
                m4 = Message.objects.create(
                    conversation=conv,
                    sender="fan",
                    text="I love it! Can we chat more?",
                    kind="text",
                )
                conv.awaiting_reply_since = now
                conv.unread_count = 1
                conv.last_message_at = now
                conv.save()
            else:
                conv.last_message_at = now
                conv.save()

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))
        self.stdout.write("")
        self.stdout.write("Demo accounts (password: demo1234):")
        self.stdout.write("  Chatters: chatter1, chatter2, chatter3, chatter4")
        self.stdout.write("  Teamlead: teamlead1")
