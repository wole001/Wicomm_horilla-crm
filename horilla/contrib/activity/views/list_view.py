"""
List views for different activity types (Task, Meeting, Call, Email, Event) in the Horilla platform.
"""

# Standard library imports
from urllib.parse import urlencode

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.functional import cached_property  # type: ignore
from django.views import View

from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.views import HorillaListView
from horilla.contrib.mail.models import HorillaMail
from horilla.contrib.utils.methods import get_section_info_for_model
from horilla.http import HttpResponse

# First party imports (Horilla)
from horilla.urls import resolve, reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

from ..filters import ActivityFilter
from ..models import Activity


class ActivityTabListMixin:
    """
    Mixin for activity tab list views (Task, Meeting, Call, Event).
    Provides a col_attrs cached_property that includes referrer params so that
    clicking a row navigates to the Activity detail view with the correct
    breadcrumb pointing back to the parent object.
    """

    _col_attrs_first_field = "title"

    @cached_property
    def col_attrs(self):
        """HTMX column attributes so row clicks open the activity detail with correct referrer."""
        object_id = self.kwargs.get("object_id")
        content_type_id = self.request.GET.get("content_type_id")

        activity_section = get_section_info_for_model(Activity).get("section", "")

        referrer_params = ""
        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                parent_model_class = content_type.model_class()
                app_label = parent_model_class._meta.app_label
                model_name = parent_model_class._meta.model_name

                parent_obj = parent_model_class.objects.filter(pk=object_id).first()
                referrer_url = ""
                if parent_obj and hasattr(parent_obj, "get_detail_url"):
                    try:
                        detail_path = str(parent_obj.get_detail_url())
                        resolved = resolve(detail_path)
                        referrer_url = resolved.url_name or ""
                    except Exception:
                        pass

                referrer_params = (
                    f"referrer_app={app_label}"
                    f"&referrer_model={model_name}"
                    f"&referrer_id={object_id}"
                    f"&referrer_url={referrer_url}"
                )
            except Exception:
                pass

        section_param = f"&section={activity_section}" if activity_section else ""
        if referrer_params:
            hx_get = f"{{get_detail_url}}?{referrer_params}{section_param}"
        else:
            hx_get = (
                f"{{get_detail_url}}?{section_param.lstrip('&')}"
                if section_param
                else "{get_detail_url}"
            )

        return [
            {
                self._col_attrs_first_field: {
                    "hx-get": hx_get,
                    "hx-target": "#mainContent",
                    "hx-swap": "outerHTML",
                    "hx-push-url": "true",
                    "hx-select": "#mainContent",
                    "hx-select-oob": "#sideMenuContainer",
                    "permission": "activity.change_activity",
                    "own_permission": "activity.change_own_activity",
                    "owner_field": "owner",
                }
            }
        ]


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class AllActivityListView(LoginRequiredMixin, HorillaListView):
    """
    Activity List view
    """

    model = Activity
    view_id = "activity-list"
    filterset_class = ActivityFilter
    search_url = reverse_lazy("activity:activity_list_view")
    main_url = reverse_lazy("activity:activity_view")
    bulk_update_fields = [
        "status",
    ]
    header_attrs = [
        {"subject": {"style": "width: 300px;"}},
    ]

    @cached_property
    def col_attrs(self):
        """
        Defines column attributes for rendering clickable Activity entries
        that load detailed views dynamically using HTMX.
        """

        query_params = {}
        if "section" in self.request.GET:
            query_params["section"] = self.request.GET.get("section")
        query_string = urlencode(query_params)
        attrs = {
            "hx-get": f"{{get_detail_url}}?{query_string}",
            "hx-target": "#mainContent",
            "hx-swap": "outerHTML",
            "hx-push-url": "true",
            "hx-select": "#mainContent",
            "permission": "activity.change_activity",
            "own_permission": "activity.change_own_activity",
            "owner_field": "owner",
        }
        return [
            {
                "subject": {
                    **attrs,
                }
            }
        ]

    columns = [
        "subject",
        "activity_type",
        (_("Related To"), "related_object"),
        (_("Status"), "status_col"),
    ]

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.change_activity",
            "own_permission": "activity.change_own_activity",
            "owner_field": ["owner", "assigned_to"],
            "attrs": """
                        hx-get="{get_activity_edit_url}?new=true"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        onclick="openModal()"
                        """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.delete_activity",
            "attrs": """
                        hx-post="{get_delete_url}"
                        hx-target="#deleteModeBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "true"}}'
                        onclick="openDeleteModeModal()"
                    """,
        },
        {
            "action": _("Duplicate"),
            "src": "assets/icons/duplicate.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.add_activity",
            "attrs": """
                            hx-get="{get_activity_edit_url}?duplicate=true"
                            hx-target="#modalBox"
                            hx-swap="innerHTML"
                            onclick="openModal()"
                            """,
        },
    ]


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class TaskListView(ActivityTabListMixin, LoginRequiredMixin, HorillaListView):
    """
    Task List view
    """

    model = Activity
    bulk_select_option = False
    paginate_by = 5
    table_width = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    list_column_visibility = False
    _col_attrs_first_field = "title"

    columns = [
        ("Title", "title"),
        ("Due Date", "due_datetime"),
        ("Priority", "task_priority"),
        (_("Status"), "status_col"),
    ]

    def get_search_url(self):
        """
        Return the search URL for the call list view.
        """
        return reverse_lazy(
            "activity:task_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    def get_main_url(self):
        """
        Return the Main URL for the call list view.
        """
        return reverse_lazy(
            "activity:task_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    @property
    def search_url(self):
        """
        Return the search URL for the call list view.
        """
        return self.get_search_url()

    @property
    def main_url(self):
        """
        Return the main URL for the call list view.
        """
        return self.get_main_url()

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.change_activity",
            "own_permission": "activity.change_own_activity",
            "owner_field": ["owner", "assigned_to"],
            "attrs": """
                        hx-get="{get_edit_url}?new=true"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        onclick="openModal()"
                        """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.delete_activity",
            "attrs": """
                        hx-post="{get_delete_url}"
                        hx-target="#deleteModeBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "true"}}'
                        onclick="openDeleteModeModal()"
                    """,
        },
    ]

    def get_queryset(self):
        status_view_map = {
            "pending": "ActivityTaskListPending",
            "completed": "ActivityTaskListCompleted",
        }

        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "pending")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id, content_type=content_type, activity_type="task"
                )
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        # Pending tab = all non-completed tasks (status is workflow: not_started, etc.)
        if view_type == "completed":
            queryset = queryset.filter(status="completed")
            self.view_id = status_view_map["completed"]
        elif view_type == "pending":
            queryset = queryset.exclude(status="completed")
            self.view_id = status_view_map["pending"]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "pending")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class MeetingListView(ActivityTabListMixin, HorillaListView):
    """
    Meeting list view
    """

    model = Activity
    paginate_by = 10
    bulk_select_option = False
    table_width = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    list_column_visibility = False
    _col_attrs_first_field = "title"

    columns = [
        ("Title", "title"),
        ("Start Date", "get_start_date"),
        ("End Date", "get_end_date"),
        (_("Meeting Link"), "meeting_link_col"),
        (_("Status"), "status_col"),
    ]

    def get_search_url(self):
        """
        Return the search URL for the call list view.
        """
        return reverse_lazy(
            "activity:meeting_list",
            kwargs={"object_id": self.kwargs["object_id"]},
        )

    def get_main_url(self):
        """
        Return the main URL for the call list view.
        """
        return reverse_lazy(
            "activity:meeting_list",
            kwargs={"object_id": self.kwargs["object_id"]},
        )

    @property
    def search_url(self):
        """
        Return the search URL for the call list view.
        """
        return self.get_search_url()

    @property
    def main_url(self):
        """
        Return the main URL for the call list view.
        """
        return self.get_main_url()

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.change_activity",
            "own_permission": "activity.change_own_activity",
            "owner_field": ["owner", "assigned_to"],
            "attrs": """
                        hx-get="{get_edit_url}?new=true"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        onclick="openModal()"
                        """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.delete_activity",
            "attrs": """
                        hx-post="{get_delete_url}"
                        hx-target="#deleteModeBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "true"}}'
                        onclick="openDeleteModeModal()"
                    """,
        },
    ]

    def get_queryset(self):
        status_view_map = {
            "pending": "ActivityMeetingListPending",
            "completed": "ActivityMeetingListCompleted",
        }

        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "pending")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id,
                    content_type=content_type,
                    activity_type="meeting",
                )
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        if view_type == "completed":
            queryset = queryset.filter(status="completed")
            self.view_id = status_view_map["completed"]
        elif view_type == "pending":
            queryset = queryset.exclude(status="completed")
            self.view_id = status_view_map["pending"]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "pending")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class CallListView(ActivityTabListMixin, HorillaListView):
    """
    List view for call activities
    """

    model = Activity
    paginate_by = 10
    bulk_select_option = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    table_width = False
    list_column_visibility = False
    _col_attrs_first_field = "call_purpose"

    columns = [
        ("Purpose", "call_purpose"),
        ("Type", "call_type"),
        ("Duration", "call_duration_display"),
        (_("Status"), "status_col"),
    ]

    def get_search_url(self):
        """
        Return the search URL for the call list view.
        """
        return reverse_lazy(
            "activity:call_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    def get_main_url(self):
        """
        Return the Main URL for the call list view.
        """
        return reverse_lazy(
            "activity:call_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    @property
    def search_url(self):
        """
        Return the search URL for the call list view.
        """
        return self.get_search_url()

    @property
    def main_url(self):
        """
        Return the main URL for the call list view.
        """
        return self.get_main_url()

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.change_activity",
            "own_permission": "activity.change_own_activity",
            "owner_field": ["owner", "assigned_to"],
            "attrs": """
                        hx-get="{get_edit_url}?new=true"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        onclick="openModal()"
                        """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.delete_activity",
            "attrs": """
                        hx-post="{get_delete_url}"
                        hx-target="#deleteModeBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "true"}}'
                        onclick="openDeleteModeModal()"
                    """,
        },
    ]

    def get_queryset(self):
        status_view_map = {
            "pending": "ActivityCallListPending",
            "completed": "ActivityCallListCompleted",
        }

        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "pending")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id,
                    content_type=content_type,
                    activity_type="log_call",
                )
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        if view_type == "completed":
            queryset = queryset.filter(status="completed")
            self.view_id = status_view_map["completed"]
        elif view_type == "pending":
            queryset = queryset.exclude(status="completed")
            self.view_id = status_view_map["pending"]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "pending")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class EmailListView(HorillaListView):
    """
    List view for email activities
    """

    model = HorillaMail
    bulk_select_option = False
    paginate_by = 10
    table_width = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    list_column_visibility = False

    columns = [
        ("Subject", "render_subject"),
        ("Send To", "to"),
        ("Sent At", "sent_at"),
        ("Status", "get_mail_status_display"),
    ]

    def get_search_url(self):
        """
        Return the search URL for the email list view.
        """
        return reverse_lazy(
            "activity:email_list",
            kwargs={"object_id": self.kwargs["object_id"]},
        )

    @property
    def search_url(self):
        """
        Return the search URL for the email list view.
        """
        return self.get_search_url()

    action_col = {
        "draft": [
            {
                "action": "Send Email",
                "src": "assets/icons/email_black.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                            hx-get="{get_edit_url}"
                            hx-target="#horillaModalBox"
                            hx-swap="innerHTML"
                            onclick="openhorillaModal()"
                            """,
            },
            {
                "action": "Delete",
                "src": "assets/icons/a4.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                        hx-post="{get_delete_url}?view=draft"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "false"}}'
                        onclick="openModal()"
                    """,
            },
        ],
        "scheduled": [
            {
                "action": "Cancel",
                "src": "assets/icons/cancel.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                        hx-get="{get_edit_url}?cancel=true"
                        hx-target="#horillaModalBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        onclick="openhorillaModal()"
                    """,
            },
            {
                "action": "Snooze",
                "src": "assets/icons/clock.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                        hx-get="{get_reschedule_url}"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        onclick="openModal()"
                    """,
            },
            {
                "action": "Delete",
                "src": "assets/icons/a4.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                        hx-post="{get_delete_url}?view=scheduled"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "false"}}'
                        onclick="openModal()"
                    """,
            },
        ],
        "sent": [
            {
                "action": "View Email",
                "src": "assets/icons/eye1.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                            hx-get="{get_view_url}"
                            hx-target="#contentModalBox"
                            hx-swap="innerHTML"
                            onclick="openContentModal()"
                            """,
            },
            {
                "action": "Delete",
                "src": "assets/icons/a4.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                hx-post="{get_delete_url}?view=sent"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                hx-trigger="click"
                hx-vals='{{"check_dependencies": "false"}}'
                onclick="openModal()"
            """,
            },
        ],
    }

    # Delivered / bounced / opened / failed share the same actions as "sent"
    action_col["delivered"] = action_col["sent"]
    action_col["bounced"] = action_col["sent"]
    action_col["opened"] = action_col["sent"]
    action_col["failed"] = action_col["sent"]

    @cached_property
    def actions(self):
        """
        Return actions based on the current view type (draft, scheduled, sent).
        """
        view_type = self.request.GET.get("view_type")
        action = self.action_col.get(view_type)
        return action

    def get_queryset(self):
        status_view_map = {
            "sent": "activity-email-list-sent",
            "draft": "activity-email-list-draft",
            "scheduled": "activity-email-list-scheduled",
        }
        # All post-send statuses shown under the "Sent" tab
        sent_statuses = ["sent", "delivered", "bounced", "opened", "failed"]

        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "sent")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id, content_type=content_type
                )
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        if view_type in status_view_map:
            if view_type == "sent":
                queryset = queryset.filter(mail_status__in=sent_statuses)
            else:
                queryset = queryset.filter(mail_status=view_type)
            self.view_id = status_view_map[view_type]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "sent")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class EventListView(ActivityTabListMixin, HorillaListView):
    """
    List view for event activities
    """

    model = Activity
    bulk_select_option = False
    paginate_by = 10
    table_width = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    list_column_visibility = False
    _col_attrs_first_field = "title"

    columns = [
        ("Title", "title"),
        ("Start Date", "get_start_date"),
        ("End Date", "get_end_date"),
        ("Location", "location"),
        # ("All day Event","is_all_day"),
        (_("Status"), "status_col"),
    ]

    def get_search_url(self):
        """
        Return the search URL for the event list view.
        """
        return reverse_lazy(
            "activity:event_list",
            kwargs={"object_id": self.kwargs["object_id"]},
        )

    @property
    def search_url(self):
        """
        Return the search URL for the event list view.
        """
        return self.get_search_url()

    actions = [
        {
            "action": "Edit",
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.change_activity",
            "own_permission": "activity.change_own_activity",
            "owner_field": ["owner", "assigned_to"],
            "attrs": """
                        hx-get="{get_edit_url}?new=true"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        onclick="openModal()"
                        """,
        },
        {
            "action": "Delete",
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "permission": "activity.delete_activity",
            "attrs": """
                        hx-post="{get_delete_url}"
                        hx-target="#deleteModeBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "true"}}'
                        onclick="openDeleteModeModal()"
                    """,
        },
    ]

    def get_queryset(self):
        status_view_map = {
            "pending": "ActivityEventListPending",
            "completed": "ActivityEventListCompleted",
        }

        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "pending")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id,
                    content_type=content_type,
                    activity_type="event",
                )
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        if view_type == "completed":
            queryset = queryset.filter(status="completed")
            self.view_id = status_view_map["completed"]
        elif view_type == "pending":
            queryset = queryset.exclude(status="completed")
            self.view_id = status_view_map["pending"]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "pending")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.change_activity", "activity.change_own_activity"]
    ),
    name="dispatch",
)
class ActivityStatusUpdateView(LoginRequiredMixin, View):
    """
    Inline status update view for activities.
    Handles HTMX POST requests from the status select dropdown in the list view.
    """

    def post(self, request, *args, **kwargs):
        """Handle POST request to update activity status inline."""
        status = request.POST.get("status")
        valid_statuses = [choice[0] for choice in Activity.STATUS_CHOICES]
        if status not in valid_statuses:
            messages.error(request, _("Invalid status."))
            return HttpResponse(status=400)

        try:
            activity = Activity.objects.get(pk=kwargs["pk"])
        except Activity.DoesNotExist:
            messages.error(request, _("Activity not found."))
            return HttpResponse(status=404)

        activity.status = status
        activity.save(update_fields=["status"])
        messages.success(
            request,
            f"Status Updated.",
        )
        tab_map = {
            "task": "tab-tasks",
            "meeting": "tab-meetings",
            "log_call": "tab-call",
            "event": "tab-events",
        }
        sub_tab = "completed" if status == "completed" else "pending"
        tab_id = tab_map.get(activity.activity_type, "")
        if tab_id:
            return HttpResponse(
                f"<script>"
                f"localStorage.setItem('horilla_active_activity_tab','{tab_id}');"
                f"localStorage.setItem('horilla_active_activity_subtab','{sub_tab}');"
                f"$('#reloadButton').click();"
                f"</script>"
            )
        return HttpResponse("<script>$('#reloadButton').click();</script>")
