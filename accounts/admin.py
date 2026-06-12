from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("CRM", {"fields": ("role", "display_name")}),
    )
    list_display = ["username", "display_name", "role", "is_active"]
