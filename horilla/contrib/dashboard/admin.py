"""Admin configuration for dashboard app."""

# Third-party imports (Django)
from django.contrib import admin

# Local imports
from .models import (
    ComponentCriteria,
    Dashboard,
    DashboardComponent,
    DashboardFolder,
    DefaultHomeLayoutOrder,
)

# Register your dashboard models here.
admin.site.register(DashboardComponent)
admin.site.register(ComponentCriteria)
admin.site.register(DefaultHomeLayoutOrder)


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    filter_horizontal = ("favourited_by",)


@admin.register(DashboardFolder)
class DashboardFolderAdmin(admin.ModelAdmin):
    filter_horizontal = ("favourited_by",)
