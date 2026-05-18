"""Admin registration for the meeting integration app."""

from django.contrib import admin

from .models import MeetingIntegrationSetting, MeetingLink, UserMeetingConfig


@admin.register(MeetingIntegrationSetting)
class MeetingIntegrationSettingAdmin(admin.ModelAdmin):
    """Configure company meeting integration toggle and permitted roles/users."""

    list_display = ("company", "is_enabled", "access_type")
    list_filter = ("is_enabled", "access_type")
    filter_horizontal = ("allowed_roles", "allowed_users")


@admin.register(UserMeetingConfig)
class UserMeetingConfigAdmin(admin.ModelAdmin):
    """Inspect per-user static meeting URLs by provider."""

    list_display = ("user", "provider", "company")
    list_filter = ("provider",)


@admin.register(MeetingLink)
class MeetingLinkAdmin(admin.ModelAdmin):
    """Browse meeting links created within the tenant."""

    list_display = ("title", "provider", "created_by_user", "start_datetime", "company")
    list_filter = ("provider",)
    search_fields = ("title",)
