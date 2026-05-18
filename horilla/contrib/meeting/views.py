"""Views for the Horilla Meeting Integration app."""

# Standard library imports
import time as _time
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

from horilla.contrib.generics.views.single_form import HorillaSingleFormView

# First party imports (Horilla)
from horilla.http import HttpResponse
from horilla.shortcuts import redirect, render
from horilla.urls import reverse, reverse_lazy
from horilla.utils.decorators import method_decorator, permission_required_or_denied
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .forms import (
    MeetingAccessRolesForm,
    MeetingAccessUsersForm,
    MeetingIntegrationSettingForm,
    MeetingLinkForm,
)
from .models import MeetingIntegrationSetting, MeetingLink, UserMeetingConfig

_ADMIN_SETTINGS_TEMPLATE = "meeting/meeting_integration_settings.html"
_USER_SETTINGS_TEMPLATE = "meeting/meeting_user_settings.html"
_CREATE_LINK_TEMPLATE = "meeting/meeting_create_link.html"
_MEETING_LIST_TEMPLATE = "meeting/meeting_link_list.html"


def _get_active_company(request):
    return getattr(request, "active_company", None) or request.user.company


def _clear_meeting_credentials(users_qs):
    """Delete all meeting OAuth data for the given user queryset."""
    from horilla.contrib.meeting.models import (
        MicrosoftTeamsOAuthConfig,
        UserMeetingConfig,
        ZoomOAuthConfig,
    )

    ZoomOAuthConfig.objects.filter(user__in=users_qs).delete()
    MicrosoftTeamsOAuthConfig.objects.filter(user__in=users_qs).delete()
    UserMeetingConfig.objects.filter(user__in=users_qs).delete()


# ─────────────────────────────────────────────────────────────
# Admin Views  (Settings → Integrations)
# ─────────────────────────────────────────────────────────────


class MeetingIntegrationSettingsView(LoginRequiredMixin, View):
    """
    Admin view: single enable/disable toggle for meeting integration
    plus access-control configuration.

    GET  — renders the settings page.
    POST — enables or disables the integration (via hx-vals),
           or saves access-type/allowed fields.
    """

    @method_decorator(
        permission_required_or_denied("meeting.change_meetingintegrationsetting")
    )
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def _render(self, request, form=None):
        from horilla.auth.models import User
        from horilla.contrib.core.models import Role

        company = _get_active_company(request)
        setting = MeetingIntegrationSetting.get_for_company(company)
        if form is None:
            form = MeetingIntegrationSettingForm(instance=setting)

        all_roles = Role.objects.filter(company=company)
        all_users = User.objects.filter(company=company, is_active=True)
        selected_role_ids = list(setting.allowed_roles.values_list("pk", flat=True))
        selected_user_ids = list(setting.allowed_users.values_list("pk", flat=True))

        context = {
            "integration_setting": setting,
            "form": form,
            "all_roles": all_roles,
            "all_users": all_users,
            "selected_role_ids": selected_role_ids,
            "selected_user_ids": selected_user_ids,
        }
        return render(request, _ADMIN_SETTINGS_TEMPLATE, context)

    def get(self, request, *args, **kwargs):
        """Render admin meeting integration settings."""
        return self._render(request)

    def post(self, request, *args, **kwargs):
        """Toggle integration, update access type, or persist related admin actions."""
        company = _get_active_company(request)
        setting = MeetingIntegrationSetting.get_for_company(company)

        # Toggle enable/disable (sent via hx-vals from the toggle buttons)
        if "is_meeting_enabled" in request.POST:
            value = request.POST.get("is_meeting_enabled") == "true"
            setting.is_enabled = value
            setting.save(update_fields=["is_enabled"])
            if value:
                messages.success(request, _("Meeting integration enabled."))
            else:
                from horilla.auth.models import User

                company_users = User.objects.filter(company=company)
                _clear_meeting_credentials(company_users)
                messages.success(
                    request,
                    _("Meeting integration disabled and all credentials cleared."),
                )
            return self._render(request)

        # "All Users" — no credentials to clear, everyone gets access
        if request.POST.get("access_type") == "all":
            setting.access_type = "all"
            setting.save(update_fields=["access_type"])
            messages.success(request, _("Access set to All Users."))
            return self._render(request)

        return self._render(request)


# ─────────────────────────────────────────────────────────────
# Access edit modals — HorillaSingleFormView style
# ─────────────────────────────────────────────────────────────


class MeetingAccessRolesView(LoginRequiredMixin, HorillaSingleFormView):
    """Modal form: select which roles can access meeting integration."""

    model = MeetingIntegrationSetting
    form_class = MeetingAccessRolesForm
    form_title = _("Select Roles")
    form_url = reverse_lazy("meeting:meeting_access_roles")
    full_width_fields = ["allowed_roles"]
    modal_height = False
    save_and_new = False

    @method_decorator(
        permission_required_or_denied("meeting.change_meetingintegrationsetting")
    )
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def _get_m2m_picker_info(self):
        return {}

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        company = _get_active_company(self.request)
        setting = MeetingIntegrationSetting.get_for_company(company)
        from horilla.contrib.core.models import Role

        form.fields["allowed_roles"].queryset = Role.objects.filter(company=company)
        form.fields["allowed_roles"].initial = setting.allowed_roles.all()
        return form

    def form_valid(self, form):
        from horilla.auth.models import User

        company = _get_active_company(self.request)
        setting = MeetingIntegrationSetting.get_for_company(company)
        new_roles = form.cleaned_data["allowed_roles"]

        # Find users whose roles are being removed
        removed_roles = setting.allowed_roles.exclude(
            pk__in=new_roles.values_list("pk", flat=True)
        )
        users_losing_access = User.objects.filter(
            company=company, role__in=removed_roles
        )

        setting.access_type = "roles"
        setting.save(update_fields=["access_type"])
        setting.allowed_roles.set(new_roles)

        if users_losing_access.exists():
            _clear_meeting_credentials(users_losing_access)

        messages.success(self.request, _("Allowed roles updated."))
        return HttpResponse("<script>closeModal(); location.reload();</script>")


class MeetingAccessUsersView(LoginRequiredMixin, HorillaSingleFormView):
    """Modal form: select which users can access meeting integration."""

    model = MeetingIntegrationSetting
    form_class = MeetingAccessUsersForm
    form_title = _("Select Users")
    form_url = reverse_lazy("meeting:meeting_access_users")
    full_width_fields = ["allowed_users"]
    modal_height = False
    save_and_new = False

    @method_decorator(
        permission_required_or_denied("meeting.change_meetingintegrationsetting")
    )
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        company = _get_active_company(self.request)
        setting = MeetingIntegrationSetting.get_for_company(company)
        from horilla.auth.models import User

        form.fields["allowed_users"].queryset = User.objects.filter(
            company=company, is_active=True
        )
        form.fields["allowed_users"].initial = setting.allowed_users.all()
        return form

    def form_valid(self, form):
        company = _get_active_company(self.request)
        setting = MeetingIntegrationSetting.get_for_company(company)
        new_users = form.cleaned_data["allowed_users"]

        # Find users being removed from the allowed list
        removed_users = setting.allowed_users.exclude(
            pk__in=new_users.values_list("pk", flat=True)
        )

        setting.access_type = "users"
        setting.save(update_fields=["access_type"])
        setting.allowed_users.set(new_users)

        if removed_users.exists():
            _clear_meeting_credentials(removed_users)

        messages.success(self.request, _("Allowed users updated."))
        return HttpResponse("<script>closeModal(); location.reload();</script>")


# ─────────────────────────────────────────────────────────────
# User / My-Settings Views
# ─────────────────────────────────────────────────────────────


def _build_provider_cards(request, company, open_provider=None):
    """Build context cards for each meeting provider."""
    from horilla.contrib.calendar.models import GoogleCalendarConfig
    from horilla.contrib.meeting.models import (
        MicrosoftTeamsOAuthConfig,
        ZoomOAuthConfig,
    )

    cards = {}

    # ── Zoom ──
    zoom = ZoomOAuthConfig.objects.filter(user=request.user).first()
    cards["zoom"] = {
        "label": _("Zoom"),
        "oauth": True,
        "has_credentials": zoom.has_credentials() if zoom else False,
        "is_connected": zoom.is_connected() if zoom else False,
        "connected_email": zoom.connected_email if zoom else "",
        "client_id": zoom.client_id if zoom else "",
        "client_secret": zoom.client_secret if zoom else "",
        "show_panel": open_provider == "zoom",
    }

    # ── Google Meet (reuses Google Calendar OAuth) ──
    gcal = GoogleCalendarConfig.objects.filter(user=request.user).first()
    gcal_connected = gcal.is_connected() if gcal else False
    meet_cfg = UserMeetingConfig.objects.filter(
        user=request.user, provider="google_meet", company=company
    ).first()
    meet_enabled = bool(meet_cfg)
    cards["google_meet"] = {
        "label": _("Google Meet"),
        "oauth": True,
        "has_credentials": gcal.is_configured() if gcal else False,
        "gcal_connected": gcal_connected,
        "is_connected": gcal_connected and meet_enabled,
        "meet_enabled": meet_enabled,
        "connected_email": gcal.google_email if gcal else "",
        "gcal_settings_url": reverse_lazy("calendar:google_calendar_settings"),
        "show_panel": open_provider == "google_meet",
    }

    # ── Microsoft Teams ──
    teams = MicrosoftTeamsOAuthConfig.objects.filter(user=request.user).first()
    cards["ms_teams"] = {
        "label": _("Microsoft Teams"),
        "oauth": True,
        "has_credentials": teams.has_credentials() if teams else False,
        "is_connected": teams.is_connected() if teams else False,
        "connected_email": teams.connected_email if teams else "",
        "client_id": teams.client_id if teams else "",
        "client_secret": teams.client_secret if teams else "",
        "tenant_id": teams.tenant_id if teams else "",
        "show_panel": open_provider == "ms_teams",
    }

    return cards


class MeetingUserSettingsView(LoginRequiredMixin, View):
    """My Settings page — OAuth connect cards per provider."""

    def _render(self, request, open_provider=None):
        company = _get_active_company(request)
        has_access = MeetingIntegrationSetting.user_can_access(request.user, company)
        context = {
            "has_access": has_access,
            "provider_cards": (
                _build_provider_cards(request, company, open_provider)
                if has_access
                else {}
            ),
        }
        return render(request, _USER_SETTINGS_TEMPLATE, context)

    def get(self, request, *args, **kwargs):
        """Show the current user's meeting OAuth and provider configuration."""
        return self._render(request)

    def post(self, request, *args, **kwargs):
        """Save OAuth credentials, disconnect providers, or toggle Google Meet linking."""
        company = _get_active_company(request)
        provider = request.POST.get("provider")
        action = request.POST.get("action", "save_credentials")

        # ── Zoom: save credentials ──
        if provider == "zoom" and action == "save_credentials":
            from horilla.contrib.meeting.models import ZoomOAuthConfig

            cfg, _created = ZoomOAuthConfig.objects.get_or_create(
                user=request.user, defaults={"company": company}
            )
            cfg.client_id = request.POST.get("client_id", "").strip()
            cfg.client_secret = request.POST.get("client_secret", "").strip()
            cfg.company = company
            cfg.save(update_fields=["client_id", "client_secret", "company"])
            messages.success(
                request, _("Zoom credentials saved. Click Connect to authorize.")
            )
            return self._render(request)

        if provider == "zoom" and action == "disconnect":
            from horilla.contrib.meeting.models import ZoomOAuthConfig

            ZoomOAuthConfig.objects.filter(user=request.user).update(
                token={}, connected_email=""
            )
            messages.success(request, _("Zoom account disconnected."))
            return self._render(request)

        # ── Google Meet: enable / disable ──
        if provider == "google_meet" and action == "enable":
            from horilla.contrib.calendar.models import GoogleCalendarConfig

            gcal = GoogleCalendarConfig.objects.filter(user=request.user).first()
            if not gcal or not gcal.is_connected():
                messages.error(
                    request, _("Connect Google Calendar first to enable Google Meet.")
                )
                return self._render(request)
            UserMeetingConfig.objects.get_or_create(
                user=request.user,
                provider="google_meet",
                defaults={"company": company, "personal_meeting_url": ""},
            )
            messages.success(
                request, _("Google Meet enabled for meeting link generation.")
            )
            return self._render(request)

        if provider == "google_meet" and action == "disable":
            UserMeetingConfig.objects.filter(
                user=request.user, provider="google_meet", company=company
            ).delete()
            messages.success(request, _("Google Meet disabled."))
            return self._render(request)

        # ── Teams: save credentials ──
        if provider == "ms_teams" and action == "save_credentials":
            from horilla.contrib.meeting.models import MicrosoftTeamsOAuthConfig

            cfg, _created = MicrosoftTeamsOAuthConfig.objects.get_or_create(
                user=request.user, defaults={"company": company}
            )
            cfg.client_id = request.POST.get("client_id", "").strip()
            cfg.client_secret = request.POST.get("client_secret", "").strip()
            cfg.tenant_id = request.POST.get("tenant_id", "common").strip()
            cfg.company = company
            cfg.save(
                update_fields=["client_id", "client_secret", "tenant_id", "company"]
            )
            messages.success(
                request, _("Teams credentials saved. Click Connect to authorize.")
            )
            return self._render(request)

        if provider == "ms_teams" and action == "disconnect":
            from horilla.contrib.meeting.models import MicrosoftTeamsOAuthConfig

            MicrosoftTeamsOAuthConfig.objects.filter(user=request.user).update(
                token={}, connected_email=""
            )
            messages.success(request, _("Teams account disconnected."))
            return self._render(request)

        return self._render(request)


# ─────────────────────────────────────────────────────────────
# Generate meeting link (called from activity form)
# ─────────────────────────────────────────────────────────────


class GenerateMeetingLinkView(LoginRequiredMixin, View):
    """
    POST: generate a meeting link for the given provider and return JSON.
    Called via fetch() from the activity meeting form.
    """

    def post(self, request, *args, **kwargs):
        """Create a Zoom, Teams, Google Meet, or manual meeting URL and return JSON."""
        from horilla.http import JsonResponse

        provider = request.POST.get("provider", "zoom")
        title = request.POST.get("title", "Meeting")
        start_dt = request.POST.get("start_datetime")
        end_dt = request.POST.get("end_datetime")

        def _parse(dt_str):
            if not dt_str:
                return None
            for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
            return None

        start = _parse(start_dt)
        end = _parse(end_dt)

        if provider == "zoom":
            from horilla.contrib.meeting.models import ZoomOAuthConfig
            from horilla.contrib.meeting.oauth.zoom import create_meeting

            config = ZoomOAuthConfig.objects.filter(user=request.user).first()
            if not config or not config.is_connected():
                return JsonResponse(
                    {
                        "error": "Zoom account not connected. Go to My Settings → Meeting to connect."
                    },
                    status=400,
                )
            url, error = create_meeting(config, title, start, end)
            if error:
                return JsonResponse({"error": error}, status=400)
            return JsonResponse({"url": url})

        if provider == "ms_teams":
            from horilla.contrib.meeting.models import MicrosoftTeamsOAuthConfig
            from horilla.contrib.meeting.oauth.teams import create_meeting

            config = MicrosoftTeamsOAuthConfig.objects.filter(user=request.user).first()
            if not config or not config.is_connected():
                return JsonResponse(
                    {
                        "error": "Teams account not connected. Go to My Settings → Meeting to connect."
                    },
                    status=400,
                )
            url, error = create_meeting(config, title, start, end)
            if error:
                return JsonResponse({"error": error}, status=400)
            return JsonResponse({"url": url})

        if provider == "google_meet":
            from horilla.contrib.calendar.models import GoogleCalendarConfig

            config = GoogleCalendarConfig.objects.filter(user=request.user).first()
            if not config or not config.is_connected():
                return JsonResponse(
                    {
                        "error": "Google account not connected. Go to My Settings → Google Calendar to connect."
                    },
                    status=400,
                )
            try:
                from horilla.contrib.calendar.google_calendar.client_settings import (
                    GOOGLE_CALENDAR_API_BASE,
                    PRIMARY_CALENDAR_ID,
                )
                from horilla.contrib.calendar.google_calendar.service import (
                    _get_oauth_session,
                )

                session = _get_oauth_session(config)
                _start = start or datetime.now(dt_timezone.utc)
                if _start.tzinfo is None:
                    _start = _start.replace(tzinfo=dt_timezone.utc)
                _end = end or (_start + timedelta(hours=1))
                if _end.tzinfo is None:
                    _end = _end.replace(tzinfo=dt_timezone.utc)

                def _fmt(d):
                    return d.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:00")

                body = {
                    "summary": title,
                    "start": {"dateTime": _fmt(_start), "timeZone": "UTC"},
                    "end": {"dateTime": _fmt(_end), "timeZone": "UTC"},
                    "conferenceData": {
                        "createRequest": {
                            "requestId": f"horilla-meet-{request.user.pk}-{int(_time.time())}",
                            "conferenceSolutionKey": {"type": "hangoutsMeet"},
                        }
                    },
                }
                url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{PRIMARY_CALENDAR_ID}/events?conferenceDataVersion=1"
                resp = session.post(url, json=body)
                resp.raise_for_status()
                result = resp.json()
                meet_url = result.get("hangoutLink") or ""
                if not meet_url:
                    for ep in result.get("conferenceData", {}).get("entryPoints", []):
                        if ep.get("entryPointType") == "video":
                            meet_url = ep.get("uri", "")
                            break
                google_event_id = result.get("id")
                if google_event_id:
                    del_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{PRIMARY_CALENDAR_ID}/events/{google_event_id}"
                    session.delete(del_url)
                if not meet_url:
                    return JsonResponse(
                        {"error": "Could not retrieve Meet link from Google."},
                        status=400,
                    )
                return JsonResponse({"url": meet_url})
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse(
            {
                "error": f"Provider '{provider}' does not support auto-generation. Please enter the URL manually."
            },
            status=400,
        )


# ─────────────────────────────────────────────────────────────
# Zoom OAuth views
# ─────────────────────────────────────────────────────────────


class ZoomAuthorizeView(LoginRequiredMixin, View):
    """Redirect user to Zoom OAuth consent screen."""

    def get(self, request, *args, **kwargs):
        """Send the browser to Zoom's authorization URL when credentials are configured."""
        from horilla.contrib.meeting.oauth.zoom import get_or_create_config, start_oauth

        config = get_or_create_config(request.user)
        if not config.has_credentials():
            messages.error(
                request, _("Please save your Zoom Client ID and Secret first.")
            )
            return redirect(reverse("meeting:meeting_user_settings"))
        auth_url = start_oauth(request)
        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(auth_url)


class ZoomCallbackView(View):
    """Handle Zoom OAuth callback."""

    def get(self, request, *args, **kwargs):
        """Exchange the callback for tokens, set flash messages, then return to settings."""
        from horilla.contrib.meeting.oauth.zoom import handle_callback

        config, error = handle_callback(request)
        if error:
            messages.error(request, f"Zoom OAuth error: {error}")
        else:
            messages.success(request, _("Zoom account connected successfully."))
        return redirect(reverse("meeting:meeting_user_settings"))


# ─────────────────────────────────────────────────────────────
# Microsoft Teams OAuth views
# ─────────────────────────────────────────────────────────────


class TeamsAuthorizeView(LoginRequiredMixin, View):
    """Redirect user to Microsoft OAuth consent screen."""

    def get(self, request, *args, **kwargs):
        """Send the browser to Microsoft's authorization URL when credentials are configured."""
        from horilla.contrib.meeting.oauth.teams import (
            get_or_create_config,
            start_oauth,
        )

        config = get_or_create_config(request.user)
        if not config.has_credentials():
            messages.error(
                request,
                _("Please save your Teams Client ID, Secret and Tenant ID first."),
            )
            return redirect(reverse("meeting:meeting_user_settings"))
        auth_url = start_oauth(request)
        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(auth_url)


class TeamsCallbackView(View):
    """Handle Microsoft Teams OAuth callback."""

    def get(self, request, *args, **kwargs):
        """Complete the OAuth dance, set flash messages, then return to settings."""
        from horilla.contrib.meeting.oauth.teams import handle_callback

        config, error = handle_callback(request)
        if error:
            messages.error(request, f"Teams OAuth error: {error}")
        else:
            messages.success(request, _("Teams account connected successfully."))
        return redirect(reverse("meeting:meeting_user_settings"))


# ─────────────────────────────────────────────────────────────
# Meeting Link CRUD
# ─────────────────────────────────────────────────────────────


class MeetingLinkListView(LoginRequiredMixin, View):
    """List all meeting links created by the current user."""

    def get(self, request, *args, **kwargs):
        """Render saved meeting links for the active company."""
        company = _get_active_company(request)
        links = MeetingLink.objects.filter(
            company=company, created_by_user=request.user
        )
        return render(request, _MEETING_LIST_TEMPLATE, {"meeting_links": links})


class MeetingLinkCreateView(LoginRequiredMixin, View):
    """Create a new meeting link (manual URL entry)."""

    def _check_access(self, request):
        company = _get_active_company(request)
        if not MeetingIntegrationSetting.user_can_access(request.user, company):
            messages.error(
                request,
                _("Meeting integration is not currently enabled for your account."),
            )
            return redirect(reverse("meeting:meeting_link_list"))
        return None

    def get(self, request, *args, **kwargs):
        """Display empty :class:`MeetingLinkForm` when the user may create links."""
        blocked = self._check_access(request)
        if blocked:
            return blocked
        return render(request, _CREATE_LINK_TEMPLATE, {"form": MeetingLinkForm()})

    def post(self, request, *args, **kwargs):
        """Validate and persist a new meeting link for the current company."""
        blocked = self._check_access(request)
        if blocked:
            return blocked
        company = _get_active_company(request)
        form = MeetingLinkForm(request.POST)
        if form.is_valid():
            link = form.save(commit=False)
            link.company = company
            link.created_by_user = request.user
            link.save()
            messages.success(request, _("Meeting link created successfully."))
            return redirect(reverse("meeting:meeting_link_list"))
        return render(request, _CREATE_LINK_TEMPLATE, {"form": form})


class MeetingLinkUpdateView(LoginRequiredMixin, View):
    """Edit an existing meeting link."""

    def _get_link(self, request, pk):
        company = _get_active_company(request)
        return MeetingLink.objects.filter(pk=pk, company=company).first()

    def get(self, request, pk, *args, **kwargs):
        """Populate the edit form for the given primary key when scoped to the company."""
        link = self._get_link(request, pk)
        if not link:
            messages.error(request, _("Meeting link not found."))
            return redirect(reverse("meeting:meeting_link_list"))
        return render(
            request,
            _CREATE_LINK_TEMPLATE,
            {"form": MeetingLinkForm(instance=link), "link": link},
        )

    def post(self, request, pk, *args, **kwargs):
        """Save edits to an existing meeting link belonging to this company."""
        link = self._get_link(request, pk)
        if not link:
            messages.error(request, _("Meeting link not found."))
            return redirect(reverse("meeting:meeting_link_list"))
        form = MeetingLinkForm(request.POST, instance=link)
        if form.is_valid():
            form.save()
            messages.success(request, _("Meeting link updated."))
            return redirect(reverse("meeting:meeting_link_list"))
        return render(request, _CREATE_LINK_TEMPLATE, {"form": form, "link": link})


class MeetingLinkDeleteView(LoginRequiredMixin, View):
    """Delete a meeting link."""

    def post(self, request, pk, *args, **kwargs):
        """Remove the meeting link if it belongs to the active company."""
        company = _get_active_company(request)
        link = MeetingLink.objects.filter(pk=pk, company=company).first()
        if link:
            link.delete()
            messages.success(request, _("Meeting link deleted."))
        else:
            messages.error(request, _("Meeting link not found."))
        return redirect(reverse("meeting:meeting_link_list"))
