"""
This module contains the views for the activity app.
"""

from horilla.contrib.activity.views.core import (
    HorillaActivitySectionView,
    ActivityDetailView,
    ActivityNavbar,
    ActivityView,
    AcivityKanbanView,
    ActivityDetailTab,
    ActivityDetailViewTabView,
    ActivityHistoryTabView,
    ActivityDeleteView,
    ActivitynNotesAndAttachments,
    MeetingAddEmailView,
    MeetingRemoveEmailView,
)
from horilla.contrib.activity.views.list_view import (
    AllActivityListView,
    EmailListView,
    CallListView,
    TaskListView,
    MeetingListView,
    EventListView,
    ActivityStatusUpdateView,
)
from horilla.contrib.activity.views.create_view import (
    TaskCreateForm,
    MeetingsCreateForm,
    CallCreateForm,
    EventCreateForm,
    ActivityCreateView,
)

__all__ = [
    "HorillaActivitySectionView",
    "ActivityDetailView",
    "ActivityNavbar",
    "ActivityView",
    "AcivityKanbanView",
    "ActivityDetailTab",
    "ActivityDetailViewTabView",
    "ActivityHistoryTabView",
    "ActivityDeleteView",
    "ActivitynNotesAndAttachments",
    "AllActivityListView",
    "EmailListView",
    "CallListView",
    "TaskListView",
    "MeetingListView",
    "EventListView",
    "TaskCreateForm",
    "MeetingsCreateForm",
    "CallCreateForm",
    "EventCreateForm",
    "ActivityCreateView",
    "ActivityStatusUpdateView",
    "MeetingAddEmailView",
    "MeetingRemoveEmailView",
]
