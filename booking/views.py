"""
Views for the horilla_booking app.
"""

# Standard library imports
import json
import logging
from datetime import date, datetime, timedelta
from functools import cached_property

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View

from horilla.contrib.generics.views import (
    HorillaListView,
    HorillaNavView,
    HorillaSingleDeleteView,
    HorillaSingleFormView,
    HorillaView,
)
from horilla.http import HttpResponse, HttpResponseRedirect, JsonResponse
from horilla.shortcuts import get_object_or_404, render
from horilla.urls import reverse_lazy

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required,
)
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .filters import BookingFilter, BookingPageFilter
from .forms import BookingPageForm
from .models import Booking, BookingPage
from .signals import booking_submitted
from .utils import _get_day_hours, get_available_slots

_get_schedule_hours = _get_day_hours

logger = logging.getLogger(__name__)

DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_LABELS = {
    "mon": _("Monday"),
    "tue": _("Tuesday"),
    "wed": _("Wednesday"),
    "thu": _("Thursday"),
    "fri": _("Friday"),
    "sat": _("Saturday"),
    "sun": _("Sunday"),
}


# ─── Settings Views ──────────────────────────────────────────────────────────


class GoToWorkingHoursView(LoginRequiredMixin, View):
    """
    Sets the Working Hours tab as active for the company tab view, then
    redirects to Company Information so the tab opens directly.
    """

    def get(self, request, *args, **kwargs):
        """Activate the Working Hours tab and redirect to Company Information."""
        from horilla.contrib.core.models import ActiveTab

        tab_path = "/company-tab-view/"
        tab_target = "tab-business-hour-view-content"
        company = getattr(request, "active_company", None) or getattr(
            request.user, "company", None
        )

        ActiveTab.objects.filter(created_by=request.user, path=tab_path).delete()
        ActiveTab.objects.create(
            created_by=request.user,
            path=tab_path,
            tab_target=tab_target,
            company=company,
        )
        return HttpResponseRedirect("/company-information/")


class BookingSettingsView(LoginRequiredMixin, View):
    """Settings page for Booking Pages — renders nav + list directly, no tabs."""

    def get(self, request, *args, **kwargs):
        """Render the booking settings page with nav and list URLs."""
        from horilla.contrib.core.models.business_hours import BusinessHour

        active_company = getattr(request, "active_company", None)
        has_business_hour = (
            BusinessHour.objects.filter(company=active_company).exists()
            if active_company
            else BusinessHour.objects.exists()
        )
        return render(
            request,
            "settings/booking_pages.html",
            {
                "nav_url": str(reverse_lazy("booking:booking_page_nav")),
                "list_url": str(reverse_lazy("booking:booking_page_list")),
                "has_business_hour": has_business_hour,
            },
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.view_bookingpage"), name="dispatch")
class BookingPageNavView(LoginRequiredMixin, HorillaNavView):
    """Horilla navbar for the Booking Pages settings view."""

    search_url = reverse_lazy("booking:booking_page_list")
    main_url = reverse_lazy("booking:booking_settings")
    filterset_class = BookingPageFilter
    model_name = "bookingpage"
    model_app_label = "booking"
    nav_width = False
    gap_enabled = False
    all_view_types = False
    recently_viewed_option = False
    filter_option = False
    one_view_only = True
    reload_option = False
    border_enabled = False

    @property
    def new_button(self):
        """Return the new-button config if the user has permission and a BusinessHour exists."""
        from horilla.contrib.core.models.business_hours import BusinessHour

        if not self.request.user.has_perm("booking.add_bookingpage"):
            return None
        active_company = getattr(self.request, "active_company", None)
        has_bh = (
            BusinessHour.objects.filter(company=active_company).exists()
            if active_company
            else BusinessHour.objects.exists()
        )
        if not has_bh:
            return None
        return {
            "url": str(reverse_lazy("booking:booking_page_create")),
            "title": _("New Booking Page"),
            "attrs": {"id": "booking-page-create"},
        }


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.view_bookingpage"), name="dispatch")
class BookingPageListView(LoginRequiredMixin, HorillaListView):
    """List view for BookingPage records in settings."""

    model = BookingPage
    view_id = "booking-page-list"
    filterset_class = BookingPageFilter
    search_url = reverse_lazy("booking:booking_page_list")
    main_url = reverse_lazy("booking:booking_settings")
    save_to_list_option = False
    bulk_select_option = False
    table_height_as_class = "h-[calc(_100vh_-_260px_)]"
    max_visible_actions = 5
    list_column_visibility = False

    columns = [
        "title",
        "host",
        (_("Duration (min)"), "duration"),
        (_("Online"), "is_online"),
        (_("Meeting Provider"), "meeting_provider"),
        (_("Active"), "is_active"),
    ]

    @cached_property
    def col_attrs(self):
        """Return column attribute overrides that make the title open the detail panel."""
        return [
            {
                "title": {
                    "hx-get": "{get_detail_url}",
                    "hx-target": "#settings-content",
                    "hx-swap": "innerHTML",
                    "permission": "booking.view_booking",
                }
            }
        ]

    actions = [
        {
            "action": _("Edit"),
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "booking.change_bookingpage",
            "attrs": """
                hx-get="{get_edit_url}"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                onclick="openModal()"
            """,
        },
        {
            "action": _("Availability"),
            "src": "assets/icons/booking-calendar.svg",
            "img_class": "w-4 h-4",
            "permission": "booking.change_bookingpage",
            "attrs": """
                hx-get="{get_availability_url}"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                onclick="openModal()"
            """,
        },
        {
            "action": _("Embed"),
            "src": "assets/icons/booking-share.svg",
            "img_class": "w-4 h-4",
            "permission": "booking.view_bookingpage",
            "attrs": """
                hx-get="{get_embed_url}"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                onclick="openModal()"
            """,
        },
        {
            "action": _("Delete"),
            "src": "assets/icons/a4.svg",
            "img_class": "w-4 h-4",
            "permission": "booking.delete_bookingpage",
            "attrs": """
                hx-post="{get_delete_url}"
                hx-target="#deleteModeBox"
                hx-swap="innerHTML"
                hx-trigger="click"
                onclick="openDeleteModeModal()"
            """,
        },
    ]


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.add_bookingpage"), name="dispatch")
class BookingPageCreateView(LoginRequiredMixin, HorillaSingleFormView):
    """Create a new BookingPage."""

    model = BookingPage
    form_class = BookingPageForm
    form_title = _("New Booking Page")
    modal_height_class = "h-[600px]"
    full_width_fields = ["description"]

    @property
    def form_url(self):
        """Return the POST URL for the create form."""
        if self.object:
            return reverse_lazy(
                "booking:booking_page_edit", kwargs={"pk": self.object.pk}
            )
        return reverse_lazy("booking:booking_page_create")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "initial" not in kwargs:
            kwargs["initial"] = {}
        kwargs["initial"]["host"] = self.request.user.pk
        return kwargs


@method_decorator(htmx_required, name="dispatch")
class BookingToggleLocationView(LoginRequiredMixin, View):
    """Return the location field partial based on the is_online checkbox state."""

    def post(self, request, *args, **kwargs):
        """Swap in or out the location field depending on is_online."""
        is_online = request.POST.get("is_online") == "on"
        location_value = request.POST.get("location", "")
        return render(
            request,
            "partials/location_field.html",
            {"show_location": not is_online, "location_value": location_value},
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.delete_bookingpage"), name="dispatch")
class BookingPageDeleteView(LoginRequiredMixin, HorillaSingleDeleteView):
    """Delete a BookingPage."""

    model = BookingPage
    success_url = reverse_lazy("booking:booking_page_list")


@method_decorator(htmx_required, name="dispatch")
class BookingToggleRescheduleCutoffView(LoginRequiredMixin, View):
    """Return reschedule_cutoff_days field based on allow_reschedule state."""

    def post(self, request, *args, **kwargs):
        """Re-render the reschedule cutoff field partial based on toggle state."""
        allow = request.POST.get("allow_reschedule") == "on"
        value = request.POST.get("reschedule_cutoff_days", "1")
        return render(
            request,
            "partials/reschedule_cutoff_field.html",
            {"show_field": allow, "field_value": value},
        )


@method_decorator(htmx_required, name="dispatch")
class BookingToggleCancelCutoffView(LoginRequiredMixin, View):
    """Return cancel_cutoff_days field based on allow_cancel state."""

    def post(self, request, *args, **kwargs):
        """Re-render the cancel cutoff field partial based on toggle state."""
        allow = request.POST.get("allow_cancel") == "on"
        value = request.POST.get("cancel_cutoff_days", "1")
        return render(
            request,
            "partials/cancel_cutoff_field.html",
            {"show_field": allow, "field_value": value},
        )


# ─── Availability ────────────────────────────────────────────────────────────


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.change_bookingpage"), name="dispatch")
class BookingAvailabilityView(LoginRequiredMixin, View):
    """
    Modal panel showing:
    - The BusinessHour schedule linked to this page
    - The ShiftHour schedule (if set — overrides BH for slot times)
    - The host's UserUnavailability blocks from the calendar app
    Hosts can add / delete unavailability blocks directly from here.
    """

    template_name = "settings/booking_availability.html"

    def get(self, request, pk):
        """Render the availability modal for the given BookingPage."""
        from horilla.contrib.calendar.models import UserAvailability

        page = get_object_or_404(BookingPage, pk=pk)
        bh = page.business_hour
        sh = page.shift_hour
        schedule = sh or bh

        # Build per-day schedule rows for display
        day_rows = []
        if schedule:
            for code in DAY_ORDER:
                start, end = _get_schedule_hours(schedule, code)
                day_rows.append(
                    {
                        "label": str(DAY_LABELS[code]),
                        "start": start,
                        "end": end,
                        "open": start is not None,
                    }
                )

        all_users = [page.host_id] + list(
            page.participants.values_list("id", flat=True)
        )
        unavailabilities = (
            UserAvailability.objects.filter(user__in=all_users)
            .select_related("user")
            .order_by("from_datetime")
        )

        return render(
            request,
            self.template_name,
            {
                "page": page,
                "business_hour": bh,
                "shift_hour": sh,
                "day_rows": day_rows,
                "unavailabilities": unavailabilities,
            },
        )


# ─── Embed / Share ────────────────────────────────────────────────────────────


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.view_bookingpage"), name="dispatch")
class BookingEmbedView(LoginRequiredMixin, View):
    """Show embed code and public URL for a BookingPage."""

    template_name = "settings/booking_embed.html"

    def get(self, request, pk):
        """Render the embed/share modal for the given BookingPage."""
        page = get_object_or_404(BookingPage, pk=pk)
        public_url = request.build_absolute_uri(
            reverse_lazy("booking:public_booking", kwargs={"slug": page.slug})
        )
        return render(
            request, self.template_name, {"page": page, "public_url": public_url}
        )


# ─── Booking List + Status Management ────────────────────────────────────────


class BookingPageDetailView(LoginRequiredMixin, View):
    """Shell: renders nav + list into #settings-content (no full page reload)."""

    def get(self, request, pk):
        """Render the booking detail shell with nav and list fragment URLs."""
        page = get_object_or_404(BookingPage, pk=pk)
        nav_url = str(reverse_lazy("booking:booking_list_nav", kwargs={"pk": pk}))
        list_url = str(reverse_lazy("booking:booking_list", kwargs={"pk": pk}))
        return render(
            request,
            "settings/booking_detail.html",
            {"page": page, "nav_url": nav_url, "list_url": list_url},
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.view_booking"), name="dispatch")
class BookingListNavView(LoginRequiredMixin, HorillaNavView):
    """Navbar for the per-BookingPage booking list."""

    model_name = "booking"
    model_app_label = "booking"
    nav_width = False
    gap_enabled = False
    all_view_types = False
    recently_viewed_option = False
    filter_option = False
    one_view_only = True
    reload_option = False
    border_enabled = False
    navbar_indication = True

    @property
    def navbar_indication_attrs(self):
        """Return HTMX attrs for the back-to-settings breadcrumb indicator."""
        return {
            "hx-get": str(reverse_lazy("booking:booking_settings")),
            "hx-target": "#settings-content",
            "hx-swap": "innerHTML",
            "hx-select": "#booking-settings-view",
            "hx-select-oob": "#settings-sidebar",
            "hx-push-url": "true",
        }

    @property
    def _nav_title(self):
        """Return the booking page title as the nav header."""
        page = get_object_or_404(BookingPage, pk=self.kwargs["pk"])
        return page.title

    @property
    def search_url(self):
        """Return the search/filter URL for the booking list."""
        return reverse_lazy("booking:booking_list", kwargs={"pk": self.kwargs["pk"]})

    @property
    def main_url(self):
        """Return the main URL for the booking page detail view."""
        return reverse_lazy(
            "booking:booking_page_detail", kwargs={"pk": self.kwargs["pk"]}
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.view_booking"), name="dispatch")
class BookingListView(LoginRequiredMixin, HorillaListView):
    """List bookings made against a specific BookingPage."""

    model = Booking
    view_id = "booking-list"
    filterset_class = BookingFilter
    save_to_list_option = False
    bulk_select_option = False
    table_height_as_class = "h-[calc(_100vh_-_260px_)]"

    columns = [
        (_("Booker"), "booker_name"),
        (_("Email"), "booker_email"),
        (_("Date & Time"), "start_datetime"),
        "status",
        (_("Meeting URL"), "meeting_url"),
    ]

    actions = [
        {
            "action": _("Change Status"),
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "booking.change_booking",
            "attrs": """
                hx-get="{get_status_url}"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                onclick="openModal()"
            """,
        },
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(booking_page_id=self.kwargs["pk"]).select_related(
            "booking_page"
        )

    @property
    def search_url(self):
        """Return the search URL scoped to this booking page's listing."""
        return reverse_lazy("booking:booking_list", kwargs={"pk": self.kwargs["pk"]})

    @property
    def main_url(self):
        """Return the main URL for this booking page's detail view."""
        return reverse_lazy(
            "booking:booking_page_detail", kwargs={"pk": self.kwargs["pk"]}
        )


class MyBookingsView(LoginRequiredMixin, HorillaView):
    """Shell page for My Bookings under My Jobs."""

    nav_url = reverse_lazy("booking:my_bookings_nav")
    list_url = reverse_lazy("booking:my_bookings_list")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.view_booking"), name="dispatch")
class MyBookingsNavView(LoginRequiredMixin, HorillaNavView):
    """Navbar partial for My Bookings."""

    _nav_title = _("My Bookings")
    search_url = reverse_lazy("booking:my_bookings_list")
    main_url = reverse_lazy("booking:my_bookings")
    model_name = "booking"
    model_app_label = "booking"
    all_view_types = False
    recently_viewed_option = False
    filter_option = False
    one_view_only = True
    reload_option = False
    search_push_url = False


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.view_booking"), name="dispatch")
class MyBookingsListView(LoginRequiredMixin, HorillaListView):
    """HTMX list partial — bookings where current user is host or participant."""

    model = Booking
    view_id = "my-bookings-list"
    filterset_class = BookingFilter
    save_to_list_option = False
    bulk_select_option = False
    list_column_visibility = False
    table_height_as_class = "h-[calc(_100vh_-_200px_)]"
    search_url = reverse_lazy("booking:my_bookings_list")
    main_url = reverse_lazy("booking:my_bookings")

    columns = [
        (_("Booking Page"), "booking_page"),
        (_("Booker"), "booker_name"),
        (_("Email"), "booker_email"),
        (_("Date & Time"), "start_datetime"),
        "status",
        (_("Meeting URL"), "meeting_url"),
    ]

    actions = [
        {
            "action": _("Change Status"),
            "src": "assets/icons/edit.svg",
            "img_class": "w-4 h-4",
            "permission": "booking.change_booking",
            "attrs": """
                hx-get="{get_status_url}"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                onclick="openModal()"
            """,
        },
    ]

    def get_queryset(self):
        from horilla.db.models import Q

        qs = super().get_queryset()
        user = self.request.user
        return (
            qs.filter(Q(booking_page__host=user) | Q(booking_page__participants=user))
            .distinct()
            .select_related("booking_page")
        )


@method_decorator(htmx_required, name="dispatch")
@method_decorator(permission_required("booking.change_booking"), name="dispatch")
class BookingStatusUpdateView(LoginRequiredMixin, View):
    """GET — show status change form. POST — update status."""

    template_name = "settings/booking_status_form.html"

    def get(self, request, pk):
        """Render the status-change form for the given Booking."""
        booking = get_object_or_404(Booking, pk=pk)
        return render(request, self.template_name, {"booking": booking})

    def post(self, request, pk):
        """Update the booking status and send a notification email if needed."""
        from .tasks import send_status_change_email

        booking = get_object_or_404(Booking, pk=pk)
        new_status = request.POST.get("status")
        valid = [s for s, _ in booking._meta.get_field("status").choices]
        if new_status in valid:
            old_status = booking.status
            booking.status = new_status
            booking.save(update_fields=["status"])
            if old_status != new_status and new_status in ("confirmed", "cancelled"):
                import threading

                threading.Thread(
                    target=send_status_change_email,
                    args=(booking, new_status),
                    daemon=True,
                ).start()
        return HttpResponse("<script>closeModal();$('#reloadButton').click();</script>")


# ─── Public Booking Views ─────────────────────────────────────────────────────


class AvailableSlotView(View):
    """
    JSON endpoint: returns available time slots for a given date.
    URL: /horilla_booking/book/<slug>/slots/?date=2026-05-20
    """

    def get(self, request, slug):
        """Return available and booked time slots as JSON for the requested date."""
        from .utils import get_all_slots

        page = get_object_or_404(BookingPage, slug=slug, is_active=True)
        date_str = request.GET.get("date", "")
        result = {"slots": [], "booked_slots": []}
        if date_str:
            try:
                selected_date = date.fromisoformat(date_str)
                data = get_all_slots(page, selected_date)
                result["slots"] = data["available"]
                result["booked_slots"] = data["booked"]
            except ValueError:
                pass

        return JsonResponse(result)


class PublicBookingView(View):
    """
    Public 3-step booking page (calendar → slots → form).
    No login required.
    """

    template_name = "public/booking_form.html"

    def _available_days_json(self, page):
        """Return a JSON array of weekday codes that have available booking hours."""
        from .utils import _WEEKDAY_CODE, _get_day_hours

        schedule = page.shift_hour or page.business_hour
        if not schedule:
            return json.dumps([])
        avail = [
            code
            for code in _WEEKDAY_CODE
            if _get_day_hours(schedule, code) != (None, None)
        ]
        return json.dumps(avail)

    def _fully_booked_dates_json(self, page):
        """Return a JSON array of ISO date strings that are within the booking window
        but have no available slots (all slots taken or max_per_day reached)."""
        import calendar as _cal

        from .utils import _WEEKDAY_CODE, _get_day_hours, get_available_slots

        today = timezone.localdate()
        max_date = today + timedelta(days=page.booking_window)
        schedule = page.shift_hour or page.business_hour
        if not schedule:
            return json.dumps([])

        fully_booked = []
        current = today
        while current <= max_date:
            day_code = _WEEKDAY_CODE[current.weekday()]
            start_time, end_time = _get_day_hours(schedule, day_code)
            if start_time is not None and end_time is not None:
                slots = get_available_slots(page, current)
                if not slots:
                    fully_booked.append(current.isoformat())
            current += timedelta(days=1)

        return json.dumps(fully_booked)

    def get(self, request, slug):
        """Render the public booking page with calendar and slot picker."""
        page = get_object_or_404(BookingPage, slug=slug, is_active=True)
        now = timezone.now()
        ctx = {
            "page": page,
            "today_iso": now.date().isoformat(),
            "max_date_iso": (
                now.date() + timedelta(days=page.booking_window)
            ).isoformat(),
            "available_days_json": self._available_days_json(page),
            "fully_booked_dates_json": self._fully_booked_dates_json(page),
        }
        return render(request, self.template_name, ctx)

    def post(self, request, slug):
        """Validate the submitted slot, create a Booking, and render the confirmation page."""
        page = get_object_or_404(BookingPage, slug=slug, is_active=True)
        booking_date_str = request.POST.get("booking_date", "")
        booking_time_str = request.POST.get("booking_time", "")
        booker_name = request.POST.get("booker_name", "").strip()
        booker_email = request.POST.get("booker_email", "").strip()
        tz_name = request.POST.get("timezone", "")

        errors = {}
        if not booker_name:
            errors["booker_name"] = _("Your name is required.")
        if not booker_email:
            errors["booker_email"] = _("Your email is required.")
        if not booking_date_str:
            errors["booking_date"] = _("Please select a date.")
        if not booking_time_str:
            errors["booking_time"] = _("Please select a time slot.")

        start_dt = None
        if booking_date_str and booking_time_str and not errors:
            try:
                from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

                local_dt = datetime.fromisoformat(
                    f"{booking_date_str}T{booking_time_str}"
                )
                try:
                    tz = (
                        ZoneInfo(tz_name)
                        if tz_name
                        else timezone.get_current_timezone()
                    )
                except (ZoneInfoNotFoundError, KeyError):
                    tz = timezone.get_current_timezone()
                start_dt = local_dt.replace(tzinfo=tz)
            except ValueError:
                errors["booking_time"] = _("Invalid date or time.")

        if start_dt and not errors:
            # Convert the booked start time to server tz to compare against generated slots
            server_tz = timezone.get_current_timezone()
            start_in_server_tz = start_dt.astimezone(server_tz)
            selected_date = start_in_server_tz.date()
            available_slots = get_available_slots(page, selected_date)
            slot_times = [s.strftime("%H:%M") for s in available_slots]
            if start_in_server_tz.strftime("%H:%M") not in slot_times:
                errors["booking_time"] = _(
                    "That slot is no longer available. Please choose another."
                )

        if errors:
            now = timezone.now()
            error_list = list(errors.values())
            ctx = {
                "page": page,
                "errors": error_list,
                "selected_date": booking_date_str,
                "selected_time": booking_time_str,
                "today_iso": now.date().isoformat(),
                "max_date_iso": (
                    now.date() + timedelta(days=page.booking_window)
                ).isoformat(),
                "available_days_json": self._available_days_json(page),
                "form": type(
                    "F",
                    (),
                    {
                        "booker_name": type("F", (), {"value": lambda: booker_name})(),
                        "booker_email": type(
                            "F", (), {"value": lambda: booker_email}
                        )(),
                    },
                )(),
            }
            return render(request, self.template_name, ctx)

        end_dt = start_dt + timedelta(minutes=page.duration)

        # Collect custom question answers
        answers = {}
        for q in page.questions or []:
            q_id = q.get("id", "")
            answers[q_id] = request.POST.get(f"q_{q_id}", "")

        booking = Booking.objects.create(
            booking_page=page,
            booker_name=booker_name,
            booker_email=booker_email,
            start_datetime=start_dt,
            end_datetime=end_dt,
            meeting_url="",
            status="pending",
            answers=answers,
            company=page.company,
            booker_timezone=tz_name,
        )

        if page.is_online and page.meeting_provider:
            try:
                from horilla.contrib.activity.views.create_view.meeting_helpers import (
                    generate_meeting_url,
                )

                class _BookingAdapter:
                    """Thin adapter so generate_meeting_url sees the fields it expects."""

                    title = page.title
                    start_datetime = booking.start_datetime
                    end_datetime = booking.end_datetime

                class _FakeView:
                    pass

                _v = _FakeView()
                _v.request = request
                meet_url = generate_meeting_url(
                    _v, page.meeting_provider, page.host, _BookingAdapter()
                )
                if meet_url:
                    booking.meeting_url = meet_url
                    booking.save(update_fields=["meeting_url"])
            except Exception:
                logger.exception(
                    "Failed to generate meeting URL for booking pk=%s", booking.pk
                )

        booking_submitted.send(
            sender=Booking,
            booker_name=booking.booker_name,
            booker_email=booking.booker_email,
            booking_instance=booking,
            company=page.company,
        )

        public_url = request.build_absolute_uri(
            reverse_lazy("booking:public_booking", kwargs={"slug": page.slug})
        )
        cancel_url = request.build_absolute_uri(
            reverse_lazy(
                "booking:booking_cancel", kwargs={"token": booking.cancellation_token}
            )
        )
        reschedule_url = request.build_absolute_uri(
            reverse_lazy(
                "booking:booking_reschedule",
                kwargs={"token": booking.cancellation_token},
            )
        )

        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            booker_tz = (
                ZoneInfo(tz_name) if tz_name else timezone.get_current_timezone()
            )
        except (ZoneInfoNotFoundError, KeyError):
            booker_tz = timezone.get_current_timezone()

        local_start = booking.start_datetime.astimezone(booker_tz)
        local_end = booking.end_datetime.astimezone(booker_tz)
        local_start_str = local_start.strftime("%B %d, %Y at %I:%M %p")
        local_end_str = local_end.strftime("%I:%M %p")

        return render(
            request,
            "public/booking_confirmed.html",
            {
                "page": page,
                "booking": booking,
                "local_start_str": f"{local_start_str} – {local_end_str}",
                "booker_tz": str(booker_tz),
                "cancel_url": cancel_url,
                "reschedule_url": reschedule_url,
                "public_url": public_url,
            },
        )


class PublicBookingCancelView(View):
    """Allow booker to cancel via cancellation_token. No login required."""

    def _is_blocked(self, booking):
        """Return True if cancellation is blocked by cutoff policy."""
        page = booking.booking_page
        if not page.allow_cancel:
            return True
        cutoff_dt = booking.start_datetime - timedelta(days=page.cancel_cutoff_days)
        return timezone.now() >= cutoff_dt

    def get(self, request, token):
        """Render the cancellation confirmation page for the given token."""
        booking = get_object_or_404(Booking, cancellation_token=token)
        if booking.status in ("cancelled", "completed"):
            return render(
                request,
                "public/booking_cancel.html",
                {"booking": booking, "already_done": True},
            )
        blocked = self._is_blocked(booking)
        return render(
            request,
            "public/booking_cancel.html",
            {"booking": booking, "already_done": False, "blocked": blocked},
        )

    def post(self, request, token):
        """Cancel the booking and send a confirmation email to the booker."""
        import threading

        from .tasks import send_status_change_email

        booking = get_object_or_404(Booking, cancellation_token=token)
        if booking.status in ("cancelled", "completed") or self._is_blocked(booking):
            return render(
                request,
                "public/booking_cancel.html",
                {"booking": booking, "already_done": True},
            )
        booking.cancellation_reason = request.POST.get("reason", "")
        booking.status = "cancelled"
        booking.save(update_fields=["status", "cancellation_reason"])
        threading.Thread(
            target=send_status_change_email,
            args=(booking, "cancelled"),
            daemon=True,
        ).start()
        return render(
            request,
            "public/booking_cancel.html",
            {"booking": booking, "cancelled": True},
        )


class PublicBookingRescheduleView(View):
    """Allow booker to reschedule via cancellation_token. No login required."""

    template_name = "public/booking_reschedule.html"

    def _is_blocked(self, booking):
        """Return True if rescheduling is blocked by cutoff policy or not allowed."""
        page = booking.booking_page
        if not page.allow_reschedule:
            return True
        cutoff_dt = booking.start_datetime - timedelta(days=page.reschedule_cutoff_days)
        return timezone.now() >= cutoff_dt

    def get(self, request, token):
        """Render the reschedule page with available days and slot picker."""
        from .utils import _WEEKDAY_CODE, _get_day_hours

        booking = get_object_or_404(Booking, cancellation_token=token)
        if booking.status in ("cancelled", "completed") or self._is_blocked(booking):
            return render(
                request, self.template_name, {"booking": booking, "blocked": True}
            )
        page = booking.booking_page
        now = timezone.now()
        bh = page.business_hour
        avail = [
            c for c in _WEEKDAY_CODE if bh and _get_day_hours(bh, c) != (None, None)
        ]
        ctx = {
            "booking": booking,
            "page": page,
            "today_iso": now.date().isoformat(),
            "max_date_iso": (
                now.date() + timedelta(days=page.booking_window)
            ).isoformat(),
            "available_days_json": json.dumps(avail),
            "blocked": False,
        }
        return render(request, self.template_name, ctx)

    def post(self, request, token):
        """Reschedule the booking to the new slot and send a confirmation email."""
        import threading

        from .tasks import send_status_change_email

        booking = get_object_or_404(Booking, cancellation_token=token)
        if booking.status in ("cancelled", "completed") or self._is_blocked(booking):
            return render(
                request, self.template_name, {"booking": booking, "blocked": True}
            )

        page = booking.booking_page
        booking_date_str = request.POST.get("booking_date", "")
        booking_time_str = request.POST.get("booking_time", "")
        errors = {}

        start_dt = None
        if booking_date_str and booking_time_str:
            try:
                local_dt = datetime.fromisoformat(
                    f"{booking_date_str}T{booking_time_str}"
                )
                tz = timezone.get_current_timezone()
                start_dt = timezone.make_aware(local_dt, tz)
            except ValueError:
                errors["booking_time"] = _("Invalid date or time.")
        else:
            errors["booking_time"] = _("Please select a date and time.")

        if start_dt and not errors:
            available_slots = get_available_slots(page, start_dt.date())
            slot_times = [s.strftime("%H:%M") for s in available_slots]
            if booking_time_str not in slot_times:
                errors["booking_time"] = _("That slot is no longer available.")

        if errors:
            now = timezone.now()
            return render(
                request,
                self.template_name,
                {
                    "booking": booking,
                    "page": page,
                    "errors": errors,
                    "today_iso": now.date().isoformat(),
                    "max_date_iso": (
                        now.date() + timedelta(days=page.booking_window)
                    ).isoformat(),
                    "blocked": False,
                    "post": request.POST,
                },
            )

        end_dt = start_dt + timedelta(minutes=page.duration)
        booking.start_datetime = start_dt
        booking.end_datetime = end_dt
        booking.status = "pending"
        booking.save(update_fields=["start_datetime", "end_datetime", "status"])

        threading.Thread(
            target=send_status_change_email,
            args=(booking, "pending"),
            daemon=True,
        ).start()

        cancel_url = request.build_absolute_uri(
            reverse_lazy(
                "booking:booking_cancel", kwargs={"token": booking.cancellation_token}
            )
        )
        return render(
            request,
            "public/booking_confirmed.html",
            {
                "page": page,
                "booking": booking,
                "cancel_url": cancel_url,
                "rescheduled": True,
            },
        )
