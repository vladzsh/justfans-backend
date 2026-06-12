from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHATTER = "chatter"
    ROLE_TEAMLEAD = "teamlead"
    ROLE_CHOICES = [
        (ROLE_CHATTER, "Chatter"),
        (ROLE_TEAMLEAD, "Team Lead"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CHATTER)
    display_name = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.username
