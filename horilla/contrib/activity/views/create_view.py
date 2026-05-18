"""
Create and update views for activities (tasks, meetings, calls, events) in the Horilla platform, with dynamic form fields based on activity type and HTMX support for seamless user experience.
"""

# Standard library imports
import datetime
from types import SimpleNamespace

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.utils.functional import cached_property  # type: ignore

# First-party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.views import HorillaSingleFormView
from horilla.db import models
from horilla.http import Http404, HttpResponse
from horilla.shortcuts import get_object_or_404, render
from horilla.urls import reverse_lazy
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _

from ..forms import ActivityCreateForm, EventForm, LogCallForm, MeetingsForm
from ..models import Activity


@method_decorator(htmx_required, name="dispatch")
class TaskCreateForm(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form view for task activity
    """

    model = Activity
    full_width_fields = ["description"]
    modal_height = False
    hidden_fields = ["object_id", "content_type", "activity_type"]
    save_and_new = False
    fields = [
        "object_id",
        "content_type",
        "title",
        "subject",
        "owner",
        "task_priority",
        "assigned_to",
        "due_datetime",
        "status",
        "description",
        "activity_type",
    ]

    @cached_property
    def form_url(self):
        """
        Return the form URL for creating or updating a task.
        """
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("activity:task_update_form", kwargs={"pk": pk})
        return reverse_lazy("activity:task_create_form")

    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get("pk")
        object_id = request.GET.get("object_id")
        model_name = request.GET.get("model_name")
        app_label = request.GET.get("app_label")

        if pk:
            try:
                activity = get_object_or_404(Activity, pk=pk)
            except Http404:
                messages.error(
                    request,
                    f"{self.model._meta.verbose_name.title()} not found or no longer exists.",
                )
                return HttpResponse(
                    "<script>$('#reloadButton').click();closeModal();</script>"
                )
            object_id = object_id or activity.object_id
            model_name = model_name or activity.content_type.model
            app_label = app_label or activity.content_type.app_label

        if object_id and model_name:
            try:
                model_class = apps.get_model(app_label=app_label, model_name=model_name)

                try:
                    instance = get_object_or_404(model_class, pk=object_id)
                except Http404:
                    messages.error(
                        request,
                        f"{self.model._meta.verbose_name.title()} not found or no longer exists.",
                    )
                    return HttpResponse(
                        "<script>$('#reloadButton').click();closeModal();</script>"
                    )

                owner_fields = getattr(model_class, "OWNER_FIELDS", ["owner"])
                user_is_owner = False

                for field in owner_fields:
                    if hasattr(instance, field):
                        value = getattr(instance, field)

                        if isinstance(value, models.Model):
                            if value.id == request.user.id:
                                user_is_owner = True
                                break
                        elif hasattr(value, "all"):
                            if request.user in value.all():
                                user_is_owner = True
                                break

                if not user_is_owner and not request.user.has_perm(
                    "activity.add_activity"
                ):
                    return render(request, "403.html")

                return super().get(request, *args, **kwargs)

            except LookupError:
                return render(request, "403.html")
        if pk:
            if not self.model.objects.filter(
                owner_id=self.request.user, pk=pk
            ).first() and not self.request.user.has_perm("activity.change_activity"):
                return super().get(request, *args, **kwargs)
        return render(request, "403.html")

    def get_initial(self):
        """Set initial form data from GET params (object_id, model_name) for task creation."""
        initial = super().get_initial()
        object_id = self.request.GET.get("object_id")
        model_name = self.request.GET.get("model_name")
        if object_id and model_name:
            initial["object_id"] = object_id
            content_type = HorillaContentType.objects.get(model=model_name.lower())
            initial["content_type"] = content_type.id
            initial["owner"] = self.request.user
            initial["activity_type"] = "task"
        return initial

    def form_valid(self, form):
        """
        Handle form submission and save the task.
        """
        super().form_valid(form)
        return HttpResponse(
            "<script>htmx.trigger('#reloadButton','click');closeModal();</script>"
        )


@method_decorator(htmx_required, name="dispatch")
class MeetingsCreateForm(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form view for meeting activity
    """

    model = Activity
    form_class = MeetingsForm
    template_name = "meeting_create_form.html"
    save_and_new = False
    fields = [
        "object_id",
        "content_type",
        "title",
        "subject",
        "start_datetime",
        "end_datetime",
        "status",
        "owner",
        "participants",
        "meeting_host",
        "is_all_day",
        "is_online",
        "location",
        "meeting_provider",
        "reminder",
        "activity_type",
    ]
    modal_height = False

    @cached_property
    def form_url(self):
        """
        Return the form URL for creating or updating a meeting.
        """
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("activity:meeting_update_form", kwargs={"pk": pk})
        return reverse_lazy("activity:meeting_create_form")

    def get_initial(self):
        """Set initial meeting form data from GET/POST, including is_all_day and related fields."""
        initial = super().get_initial()
        if self.request.method == "POST":
            initial["is_all_day"] = self.request.POST.get("is_all_day") == "on"
            initial["is_online"] = self.request.POST.get("is_online") == "on"
        else:
            object_id = self.request.GET.get("object_id")
            model_name = self.request.GET.get("model_name")
            all_day = self.request.GET.get("is_all_day")
            toggle_is_all_day = self.request.GET.get("toggle_is_all_day")
            toggle_is_online = self.request.GET.get("toggle_is_online")

            content_type_for_initial = None
            if object_id and not model_name:
                ct_param = self.request.GET.get("content_type")
                if ct_param:
                    try:
                        content_type_for_initial = HorillaContentType.objects.get(
                            pk=int(ct_param)
                        )
                        model_name = content_type_for_initial.model
                    except (HorillaContentType.DoesNotExist, ValueError, TypeError):
                        pass

            if toggle_is_all_day == "true" and self.kwargs.get("pk"):
                initial["is_all_day"] = False
            elif all_day is not None:
                initial["is_all_day"] = all_day == "on"
            elif hasattr(self, "object") and self.object:
                initial["is_all_day"] = self.object.is_all_day

            if toggle_is_online == "true" and self.kwargs.get("pk"):
                initial["is_online"] = False
            elif self.request.GET.get("is_online") is not None:
                initial["is_online"] = self.request.GET.get("is_online") == "on"
            elif hasattr(self, "object") and self.object:
                initial["is_online"] = self.object.is_online

            if object_id and model_name:
                initial["object_id"] = object_id
                if content_type_for_initial is not None:
                    initial["content_type"] = content_type_for_initial.id
                else:
                    ct_row = HorillaContentType.objects.get(model=model_name.lower())
                    initial["content_type"] = ct_row.id
                initial["activity_type"] = "meeting"
                initial["owner"] = self.request.user

        return initial

    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get("pk")
        object_id = request.GET.get("object_id")
        model_name = request.GET.get("model_name")
        app_label = request.GET.get("app_label")

        # HTMX (e.g. is_all_day) hx-include only serializes form fields; model_name /
        # app_label are not inputs and were only on the initial URL. Recover them
        # from content_type so partial GETs still pass the gate below.
        if object_id and not model_name:
            ct_param = request.GET.get("content_type")
            if ct_param:
                try:
                    ct = HorillaContentType.objects.get(pk=int(ct_param))
                    model_name = ct.model
                    app_label = app_label or ct.app_label
                except (HorillaContentType.DoesNotExist, ValueError, TypeError):
                    pass

        if pk:
            try:
                activity = get_object_or_404(Activity, pk=pk)
            except Http404:
                messages.error(
                    request,
                    f"{self.model._meta.verbose_name.title()} not found or no longer exists.",
                )
                return HttpResponse(
                    "<script>$('#reloadButton').click();closeModal();</script>"
                )
            object_id = object_id or activity.object_id
            model_name = model_name or activity.content_type.model
            app_label = app_label or activity.content_type.app_label

        if object_id and model_name:
            try:
                model_class = apps.get_model(app_label=app_label, model_name=model_name)
                try:
                    instance = get_object_or_404(model_class, pk=object_id)
                except Http404:
                    messages.error(
                        request,
                        f"{self.model._meta.verbose_name.title()} not found or no longer exists.",
                    )
                    return HttpResponse(
                        "<script>$('#reloadButton').click();closeModal();</script>"
                    )

                owner_fields = getattr(model_class, "OWNER_FIELDS", ["owner"])
                user_is_owner = False

                for field in owner_fields:
                    if hasattr(instance, field):
                        value = getattr(instance, field)

                        if isinstance(value, models.Model):
                            if value.id == request.user.id:
                                user_is_owner = True
                                break
                        elif hasattr(value, "all"):
                            if request.user in value.all():
                                user_is_owner = True
                                break

                if not user_is_owner and not request.user.has_perm(
                    "activity.add_activity"
                ):
                    return render(request, "403.html")

                return super().get(request, *args, **kwargs)

            except LookupError:
                return render(request, "403.html")
        if pk:
            if not self.model.objects.filter(
                owner_id=self.request.user, pk=pk
            ).first() and not self.request.user.has_perm("activity.change_activity"):
                return super().get(request, *args, **kwargs)
        return render(request, "403.html")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = getattr(self, "object", None)
        existing = (
            instance.external_participants if instance and instance.pk else None
        ) or []
        if not isinstance(existing, list):
            existing = []
        context["ext_email_list"] = existing
        context["ext_email_string"] = ",".join(existing)
        return context

    def form_valid(self, form):
        """
        Auto-generate meeting URL for OAuth providers before base class saves,
        then send invite emails to external participants.
        """
        provider = form.cleaned_data.get("meeting_provider") or ""
        is_online = form.cleaned_data.get("is_online", False)

        # Capture datetime from cleaned_data now — available before and after save
        start_dt = form.cleaned_data.get("start_datetime")
        end_dt = form.cleaned_data.get("end_datetime")

        generated_url = ""
        if is_online and provider:
            activity = form.save(commit=False)
            activity.start_datetime = start_dt
            activity.end_datetime = end_dt
            host = activity.meeting_host or self.request.user
            generated_url = self._generate_url(provider, host, activity) or ""
            if generated_url:
                form.instance.meeting_url = generated_url

        # Persist external_participants from cleaned_data into the instance
        external_emails = form.cleaned_data.get("external_participants") or []
        form.instance.external_participants = external_emails

        super().form_valid(form)

        # Guarantee meeting_url is written — ModelForm only saves its own Meta.fields
        if generated_url and form.instance.pk:
            Activity.objects.filter(pk=form.instance.pk).update(
                meeting_url=generated_url
            )
            form.instance.meeting_url = generated_url

        # Send invite emails after save so we have pk and final meeting_url
        participant_emails = list(
            form.instance.participants.exclude(email="").values_list("email", flat=True)
        )
        all_recipients = list(dict.fromkeys(participant_emails + external_emails))
        if all_recipients:
            # Pass datetime from cleaned_data so invite shows correct time even if
            # form.instance.start_datetime wasn't persisted yet when we read it
            form.instance.start_datetime = form.instance.start_datetime or start_dt
            form.instance.end_datetime = form.instance.end_datetime or end_dt
            self._send_invites(form.instance, all_recipients)

        return HttpResponse(
            "<script>htmx.trigger('#MeetingsTab','click');closeModal();</script>"
        )

    def _send_invites(self, activity, emails):
        """Send an HTML meeting invitation via the configured outgoing mail server."""
        from django.conf import settings
        from django.core.mail import EmailMultiAlternatives, get_connection

        if not emails:
            return

        # Resolve outgoing mail config
        mail_config = None
        try:
            from horilla.contrib.mail.models import HorillaMailConfiguration

            company = getattr(self.request.user, "company", None)
            mail_config = (
                HorillaMailConfiguration.objects.filter(
                    company=company, mail_channel="outgoing", is_primary=True
                ).first()
                or HorillaMailConfiguration.objects.filter(
                    mail_channel="outgoing", is_primary=True
                ).first()
                or HorillaMailConfiguration.objects.filter(
                    mail_channel="outgoing"
                ).first()
            )
        except Exception:
            pass

        title = activity.title or activity.subject or "Meeting"
        meeting_url = activity.meeting_url or ""
        start = activity.start_datetime
        end = activity.end_datetime
        host_user = activity.meeting_host or self.request.user
        host_name = str(host_user)

        # Convert UTC datetimes to the host user's local timezone
        def _to_local(dt):
            if not dt:
                return None
            try:
                from zoneinfo import ZoneInfo

                tz_name = getattr(host_user, "time_zone", None)
                if tz_name:
                    return dt.astimezone(ZoneInfo(tz_name))
            except Exception:
                pass
            return timezone.localtime(dt)

        local_start = _to_local(start)
        local_end = _to_local(end)
        start_str = (
            local_start.strftime("%A, %B %d, %Y at %I:%M %p") if local_start else "TBD"
        )
        end_str = local_end.strftime("%I:%M %p") if local_end else ""
        time_line = f"{start_str}{' – ' + end_str if end_str else ''}"

        company = getattr(self.request, "active_company", None) or getattr(
            self.request.user, "company", None
        )
        company_name = str(company) if company else "Horilla CRM"

        html_body = f"""
<div style="max-width:650px;margin:auto;background:white;border-radius:12px;padding:35px;box-shadow:0 4px 12px rgba(0,0,0,0.08)">
  <h2 style="color:#000000;text-align:center;font-size:24px;margin-bottom:25px">
    Meeting Invitation
  </h2>

  <p style="font-size:14px;color:#333;line-height:1.6">
    You have been invited to a meeting by <strong>{host_name}</strong>.
  </p>

  <div style="margin:20px 0;padding:15px;background:#fdf2f1;border-left:4px solid #e54f38;border-radius:6px">
    <p style="margin:6px 0;font-size:14px;color:#333">
      &#128197; <strong>Title:</strong> {title}
    </p>
    <p style="margin:6px 0;font-size:14px;color:#333">
      &#128336; <strong>When:</strong> {time_line}
    </p>
    <p style="margin:6px 0;font-size:14px;color:#333">
      &#128100; <strong>Host:</strong> {host_name}
    </p>
    {f'<p style="margin:6px 0;font-size:14px;color:#333">&#128279; <strong>Join Link:</strong> <a href="{meeting_url}" style="color:#e54f38;">{meeting_url}</a></p>' if meeting_url else ''}
  </div>

  {f'<div style="text-align:center;margin-top:25px"><a href="{meeting_url}" style="display:inline-block;padding:10px 20px;background-color:#e54f38;color:white;text-decoration:none;border-radius:6px;font-weight:500;margin:5px">Join Meeting</a></div>' if meeting_url else ''}

  <hr style="margin:30px 0;border:none;border-top:1px solid #eee">

  <p style="font-size:12px;color:#888;text-align:center;line-height:1.5">
    This invitation was sent via <strong>{company_name}</strong>.<br>
    If you were not expecting this, please ignore this email.
  </p>
</div>"""

        plain_body = (
            f"You have been invited to a meeting by {host_name}.\n\n"
            f"Title: {title}\nWhen: {time_line}\nHost: {host_name}\n"
            + (f"Join: {meeting_url}\n" if meeting_url else "")
        )

        from_email = (
            mail_config.from_email
            if mail_config and mail_config.from_email
            else getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
        )

        try:
            connection = (
                get_connection(
                    "horilla.contrib.mail.backends.HorillaDefaultMailBackend"
                )
                if mail_config
                else get_connection()
            )

            msg = EmailMultiAlternatives(
                subject=f"Meeting Invitation: {title}",
                body=plain_body,
                from_email=from_email,
                to=emails,
                connection=connection,
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=True)
        except Exception:
            pass

    def _generate_url(self, provider, host, activity):
        """Call the appropriate OAuth API to create a meeting link."""
        title = activity.title or activity.subject or "Meeting"
        start = activity.start_datetime
        end = activity.end_datetime
        try:
            if provider == "zoom":
                from horilla.contrib.meeting.models import ZoomOAuthConfig
                from horilla.contrib.meeting.oauth.zoom import create_meeting

                config = ZoomOAuthConfig.objects.filter(user=host).first()
                if config and config.is_connected():
                    url, _ = create_meeting(config, title, start, end)
                    return url or ""
            elif provider == "ms_teams":
                from horilla.contrib.meeting.models import MicrosoftTeamsOAuthConfig
                from horilla.contrib.meeting.oauth.teams import create_meeting

                config = MicrosoftTeamsOAuthConfig.objects.filter(user=host).first()
                if config and config.is_connected():
                    url, error = create_meeting(config, title, start, end)
                    if error:
                        messages.error(self.request, error)
                    return url or ""
            elif provider == "google_meet":
                import time as _time
                from datetime import datetime as _dt
                from datetime import timedelta as _td
                from datetime import timezone as _tz

                from horilla.contrib.calendar.google_calendar.client_settings import (
                    GOOGLE_CALENDAR_API_BASE,
                    PRIMARY_CALENDAR_ID,
                )
                from horilla.contrib.calendar.google_calendar.service import (
                    _get_oauth_session,
                )
                from horilla.contrib.calendar.models import GoogleCalendarConfig

                config = GoogleCalendarConfig.objects.filter(user=host).first()
                if config and config.is_connected():
                    session = _get_oauth_session(config)
                    _start = start or _dt.now(_tz.utc)
                    _end = end or (_start + _td(hours=1))

                    # Convert to UTC ISO string
                    def _fmt(d):
                        return d.astimezone(_tz.utc).strftime("%Y-%m-%dT%H:%M:00")

                    body = {
                        "summary": title,
                        "start": {"dateTime": _fmt(_start), "timeZone": "UTC"},
                        "end": {"dateTime": _fmt(_end), "timeZone": "UTC"},
                        "conferenceData": {
                            "createRequest": {
                                "requestId": f"horilla-meet-{host.pk}-{int(_time.time())}",
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
                        for ep in result.get("conferenceData", {}).get(
                            "entryPoints", []
                        ):
                            if ep.get("entryPointType") == "video":
                                meet_url = ep.get("uri", "")
                                break
                    # Delete the Google Calendar event — we only needed it to provision the Meet link
                    google_event_id = result.get("id")
                    if google_event_id:
                        del_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{PRIMARY_CALENDAR_ID}/events/{google_event_id}"
                        session.delete(del_url)
                    return meet_url
        except Exception:
            pass
        return ""


@method_decorator(htmx_required, name="dispatch")
class CallCreateForm(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form view for call activity
    """

    model = Activity
    form_class = LogCallForm
    modal_height = False
    full_width_fields = ["notes"]
    save_and_new = False

    fields = [
        "object_id",
        "content_type",
        "subject",
        "owner",
        "call_purpose",
        "call_type",
        "call_duration_display",
        "status",
        "notes",
        "activity_type",
    ]

    @cached_property
    def form_url(self):
        """
        Return the form URL for creating or updating a call.
        """
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("activity:call_update_form", kwargs={"pk": pk})
        return reverse_lazy("activity:call_create_form")

    def get_initial(self):
        """Set initial call form data from GET params and default duration for new calls."""
        initial = super().get_initial()
        object_id = self.request.GET.get("object_id")
        model_name = self.request.GET.get("model_name")
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if not pk:
            initial["call_duration_display"] = (
                "00:00:00"  # Default duration for creation
            )

        if object_id and model_name:
            initial["object_id"] = object_id
            content_type = HorillaContentType.objects.get(model=model_name.lower())
            initial["content_type"] = content_type.id
            initial["activity_type"] = "log_call"
            initial["owner"] = self.request.user

        return initial

    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get("pk")
        object_id = request.GET.get("object_id")
        model_name = request.GET.get("model_name")
        app_label = request.GET.get("app_label")

        if pk:
            try:
                activity = get_object_or_404(Activity, pk=pk)
            except Http404:
                messages.error(
                    request,
                    f"{self.model._meta.verbose_name.title()} not found or no longer exists.",
                )
                return HttpResponse(
                    "<script>$('#reloadButton').click();closeModal();</script>"
                )
            object_id = object_id or activity.object_id
            model_name = model_name or activity.content_type.model
            app_label = app_label or activity.content_type.app_label

        if object_id and model_name:
            try:
                model_class = apps.get_model(app_label=app_label, model_name=model_name)
                try:
                    instance = get_object_or_404(model_class, pk=object_id)
                except Http404:
                    messages.error(
                        request,
                        f"{self.model._meta.verbose_name.title()} not found or no longer exists.",
                    )
                    return HttpResponse(
                        "<script>$('#reloadButton').click();closeModal();</script>"
                    )

                owner_fields = getattr(model_class, "OWNER_FIELDS", ["owner"])
                user_is_owner = False

                for field in owner_fields:
                    if hasattr(instance, field):
                        value = getattr(instance, field)

                        if isinstance(value, models.Model):
                            if value.id == request.user.id:
                                user_is_owner = True
                                break
                        elif hasattr(value, "all"):
                            if request.user in value.all():
                                user_is_owner = True
                                break

                if not user_is_owner and not request.user.has_perm(
                    "activity.add_activity"
                ):
                    return render(request, "403.html")

                return super().get(request, *args, **kwargs)

            except LookupError:
                return render(request, "403.html")
        if pk:
            if not self.model.objects.filter(
                owner_id=self.request.user, pk=pk
            ).first() and not self.request.user.has_perm("activity.change_activity"):
                return super().get(request, *args, **kwargs)
        return render(request, "403.html")

    def form_valid(self, form):
        """
        Handle form submission and save the meeting.
        """
        super().form_valid(form)
        return HttpResponse(
            "<script>htmx.trigger('#CallsTab','click');closeModal();</script>"
        )


@method_decorator(htmx_required, name="dispatch")
class EventCreateForm(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form view for event activity
    """

    model = Activity
    form_class = EventForm
    modal_height = False
    full_width_fields = ["notes"]
    save_and_new = False

    fields = [
        "object_id",
        "content_type",
        "title",
        "subject",
        "owner",
        "start_datetime",
        "end_datetime",
        "location",
        "assigned_to",
        "status",
        "is_all_day",
        "activity_type",
    ]

    @cached_property
    def form_url(self):
        """
        Return the form URL for creating or updating an event.
        """
        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("activity:event_update_form", kwargs={"pk": pk})
        return reverse_lazy("activity:event_create_form")

    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get("pk")
        object_id = request.GET.get("object_id")
        model_name = request.GET.get("model_name")
        app_label = request.GET.get("app_label")

        if pk:
            try:
                activity = get_object_or_404(Activity, pk=pk)
            except Http404:
                messages.error(
                    request,
                    f"{self.model._meta.verbose_name.title()} not found or no longer exists.",
                )
                return HttpResponse(
                    "<script>$('#reloadButton').click();closeModal();</script>"
                )
            object_id = object_id or activity.object_id
            model_name = model_name or activity.content_type.model
            app_label = app_label or activity.content_type.app_label

        if object_id and model_name:
            try:
                model_class = apps.get_model(app_label=app_label, model_name=model_name)

                try:
                    instance = get_object_or_404(model_class, pk=object_id)
                except Http404:
                    messages.error(
                        request,
                        f"{self.model._meta.verbose_name.title()} not found or no longer exists.",
                    )
                    return HttpResponse(
                        "<script>$('#reloadButton').click();closeModal();</script>"
                    )

                owner_fields = getattr(model_class, "OWNER_FIELDS", ["owner"])
                user_is_owner = False

                for field in owner_fields:
                    if hasattr(instance, field):
                        value = getattr(instance, field)

                        if isinstance(value, models.Model):
                            if value.id == request.user.id:
                                user_is_owner = True
                                break
                        elif hasattr(value, "all"):
                            if request.user in value.all():
                                user_is_owner = True
                                break

                if not user_is_owner and not request.user.has_perm(
                    "activity.add_activity"
                ):
                    return render(request, "403.html")

                return super().get(request, *args, **kwargs)

            except LookupError:
                return render(request, "403.html")
        if pk:
            if not self.model.objects.filter(
                owner_id=self.request.user, pk=pk
            ).first() and not self.request.user.has_perm("activity.change_activity"):
                return super().get(request, *args, **kwargs)
        return render(request, "403.html")

    def get_initial(self):
        """Set initial event form data from GET/POST, including is_all_day and related fields."""
        initial = super().get_initial()
        if self.request.method == "POST":
            initial["is_all_day"] = self.request.POST.get("is_all_day") == "on"
        else:
            object_id = self.request.GET.get("object_id")
            model_name = self.request.GET.get("model_name")
            all_day = self.request.GET.get("is_all_day")
            toggle_is_all_day = self.request.GET.get("toggle_is_all_day")

            # If toggle_is_all_day is present and we're in edit mode, force is_all_day to False
            if toggle_is_all_day == "true" and self.kwargs.get("pk"):
                initial["is_all_day"] = False

            # If we have GET parameter for is_all_day, use it
            elif all_day is not None:
                initial["is_all_day"] = all_day == "on"

            # If we're editing an existing event and no GET parameter, use the model value
            elif hasattr(self, "object") and self.object:
                initial["is_all_day"] = self.object.is_all_day

            if object_id and model_name:
                initial["object_id"] = object_id
                content_type = HorillaContentType.objects.get(model=model_name.lower())
                initial["content_type"] = content_type.id
                initial["activity_type"] = "event"
                initial["owner"] = self.request.user

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == "POST":
            return kwargs

        initial = self.get_initial()
        get_data = self.request.GET.dict()
        for key, value in get_data.items():
            if value:
                initial[key] = value
        kwargs["initial"] = initial
        return kwargs

    def form_valid(self, form):
        """
        Handle form submission and save the meeting.
        """

        super().form_valid(form)
        return HttpResponse(
            "<script>htmx.trigger('#EventTab','click');closeModal();</script>"
        )


@method_decorator(htmx_required, name="dispatch")
class ActivityCreateView(LoginRequiredMixin, HorillaSingleFormView):
    """
    Form view for creating and updating activities with dynamic fields based on activity type.
    """

    model = Activity
    form_class = ActivityCreateForm
    template_name = "activity_create_form.html"
    success_url = reverse_lazy("activity:activity_list")
    view_id = "activity-form-view"
    save_and_new = False
    full_width_fields = ["description", "notes"]

    ACTIVITY_FIELD_MAP = {
        "event": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "owner",
            "status",
            "title",
            "start_datetime",
            "end_datetime",
            "location",
            "is_all_day",
            "assigned_to",
            "participants",
            "description",
        ],
        # Mirrors MeetingsCreateForm / MeetingsForm (pills + provider + online are not on this template).
        "meeting": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "owner",
            "status",
            "title",
            "start_datetime",
            "end_datetime",
            "meeting_host",
            "is_all_day",
            "is_online",
            "location",
            "meeting_provider",
            "participants",
            "reminder",
            "description",
        ],
        "task": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "status",
            "owner",
            "task_priority",
            "due_datetime",
            "description",
        ],
        "email": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "status",
            "sender",
            "to_email",
            "email_subject",
            "body",
            "bcc",
            "sent_at",
            "scheduled_at",
            "is_sent",
            "description",
        ],
        "log_call": [
            "activity_type",
            "subject",
            "content_type",
            "object_id",
            "owner",
            "status",
            "call_duration_display",
            "call_duration_seconds",
            "call_type",
            "call_purpose",
            "notes",
            "description",
        ],
    }

    def get_initial(self):
        """Set initial form data for create/edit, including is_all_day, date, and activity_type."""
        initial = super().get_initial()

        is_create = not (self.kwargs.get("pk") or self.object)

        if self.request.method == "POST":
            initial["is_all_day"] = self.request.POST.get("is_all_day") == "on"
            initial["is_online"] = self.request.POST.get("is_online") == "on"
        else:
            object_id = self.request.GET.get("object_id")
            model_name = self.request.GET.get("model_name")
            all_day = self.request.GET.get("is_all_day")
            toggle_is_all_day = self.request.GET.get("toggle_is_all_day")
            # Use same param as Mark Unavailability (start_date_time) so clicked time is correct
            date_str = self.request.GET.get("start_date_time") or self.request.GET.get(
                "date"
            )

            if is_create:
                initial["activity_type"] = (
                    self.request.GET.get("activity_type") or "event"
                )
                initial["owner"] = self.request.user
            else:
                initial["activity_type"] = getattr(
                    self.object, "activity_type", None
                ) or initial.get("activity_type", "event")

            if toggle_is_all_day == "true" and self.kwargs.get("pk"):
                initial["is_all_day"] = False
            elif all_day is not None:
                initial["is_all_day"] = all_day == "on"
            elif hasattr(self, "object") and self.object:
                initial["is_all_day"] = self.object.is_all_day

            toggle_is_online = self.request.GET.get("toggle_is_online")
            if toggle_is_online == "true" and self.kwargs.get("pk"):
                initial["is_online"] = False
            elif self.request.GET.get("is_online") is not None:
                initial["is_online"] = self.request.GET.get("is_online") == "on"
            elif hasattr(self, "object") and self.object:
                initial["is_online"] = getattr(self.object, "is_online", False)

            if (
                is_create
                and self.request.GET.get("activity_type") == "meeting"
                and self.request.GET.get("is_online") is None
            ):
                initial["is_online"] = False

            if is_create and date_str:
                try:
                    clicked_datetime = datetime.datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                    clicked_date = clicked_datetime.date()
                    clicked_time = clicked_datetime.time()
                    if clicked_time == datetime.time.min:
                        clicked_time = datetime.time(9, 0)
                    start_datetime = timezone.make_aware(
                        datetime.datetime.combine(clicked_date, clicked_time)
                    )
                    end_datetime = start_datetime + datetime.timedelta(minutes=30)

                    initial["start_datetime"] = start_datetime
                    initial["end_datetime"] = end_datetime
                    # Keep task deadline aligned with calendar slot defaults.
                    initial["due_datetime"] = end_datetime
                except (ValueError, TypeError):
                    pass

            if object_id and model_name:
                initial["object_id"] = object_id
                content_type = HorillaContentType.objects.get(model=model_name.lower())
                initial["content_type"] = content_type.id

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        activity_type = (
            self.request.POST.get("activity_type")
            or self.request.GET.get("activity_type")
            or (getattr(self, "object", None) and self.object.activity_type)
            or getattr(self, "activity_type", None)
        )
        if not activity_type:
            activity_type = list(self.ACTIVITY_FIELD_MAP.keys())[0]

        # Pass the list of fields that should remain visible for this activity_type
        # to the form. The form will hide all other fields.
        selected_fields = self.ACTIVITY_FIELD_MAP.get(
            activity_type, self.ACTIVITY_FIELD_MAP["event"]
        )
        kwargs["visible_fields"] = selected_fields

        kwargs["initial"] = kwargs.get("initial", {})
        kwargs["initial"]["activity_type"] = activity_type

        if self.request.method == "GET":
            kwargs["initial"] = kwargs.get("initial", {})
            for field in self.ACTIVITY_FIELD_MAP.get(
                activity_type, self.ACTIVITY_FIELD_MAP["event"]
            ):
                if field == "is_online" and field in self.request.GET:
                    kwargs["initial"][field] = self.request.GET.get("is_online") == "on"
                    continue
                if field in self.request.GET:
                    value = self.request.GET.get(field)
                    if value:
                        if field in ["start_datetime", "end_datetime"] and kwargs[
                            "initial"
                        ].get("is_all_day"):
                            continue
                        kwargs["initial"][field] = value
                elif field in self.request.GET.getlist(field):
                    values = self.request.GET.getlist(field)
                    if values:
                        kwargs["initial"][field] = values

            # New activity + meeting type: default to in-person unless is_online is in the query.
            if (
                activity_type == "meeting"
                and "is_online" not in self.request.GET
                and not (self.kwargs.get("pk") or self.request.GET.get("id"))
            ):
                kwargs["initial"]["is_online"] = False

            # Preserve date/time values across activity-type transitions
            # even when the current type does not expose those fields.
            for field in ["start_datetime", "end_datetime", "due_datetime"]:
                if field in self.request.GET:
                    value = self.request.GET.get(field)
                    if value:
                        kwargs["initial"][field] = value
            if "content_type" in self.request.GET:
                kwargs["initial"]["content_type"] = self.request.GET.get("content_type")
            if "object_id" in self.request.GET:
                kwargs["initial"]["object_id"] = self.request.GET.get("object_id")

            if (
                self.duplicate_mode
                and "initial" in kwargs
                and "content_type" in kwargs["initial"]
            ):
                content_type_value = kwargs["initial"]["content_type"]
                if hasattr(content_type_value, "id"):
                    kwargs["initial"]["content_type"] = content_type_value.id
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_url"] = self.form_url
        context["modal_height"] = True
        context["view_id"] = self.view_id
        activity_type = (
            self.request.POST.get("activity_type")
            or self.request.GET.get("activity_type")
            or (
                getattr(self.object, "activity_type", None)
                if getattr(self, "object", None)
                else None
            )
            or "event"
        )
        show_meeting = activity_type == "meeting"
        context["show_meeting_extras"] = show_meeting
        if show_meeting:
            instance = getattr(self, "object", None)
            existing = (
                instance.external_participants if instance and instance.pk else None
            ) or []
            if not isinstance(existing, list):
                existing = []
            context["ext_email_list"] = existing
            context["ext_email_string"] = ",".join(existing)
        return context

    @cached_property
    def form_url(self):
        """
        Returns the appropriate form URL for creating or editing an Activity
        based on the presence of a primary key (pk).
        """

        pk = self.kwargs.get("pk") or self.request.GET.get("id")
        if pk:
            return reverse_lazy("activity:activity_edit_form", kwargs={"pk": pk})
        return reverse_lazy("activity:activity_create_form")

    def _prepare_meeting_activity(self, form):
        """Set meeting URL and external participants on the instance before save."""
        provider = form.cleaned_data.get("meeting_provider") or ""
        is_online = form.cleaned_data.get("is_online", False)
        start_dt = form.cleaned_data.get("start_datetime")
        end_dt = form.cleaned_data.get("end_datetime")
        external_emails = form.cleaned_data.get("external_participants") or []
        inst = form.instance
        inst.external_participants = external_emails
        inst.activity_type = "meeting"
        form._meeting_generated_url = ""
        if is_online and provider:
            inst.start_datetime = start_dt
            inst.end_datetime = end_dt
            host = inst.meeting_host or self.request.user
            bridge = SimpleNamespace(request=self.request)
            url = MeetingsCreateForm._generate_url(bridge, provider, host, inst) or ""
            form._meeting_generated_url = url
            if url:
                inst.meeting_url = url

    def _after_meeting_activity_save(self, form):
        """Persist generated meeting link and send invites (same as MeetingsCreateForm)."""
        inst = self.object
        if not inst or not inst.pk:
            return
        generated_url = getattr(form, "_meeting_generated_url", "") or ""
        if generated_url:
            Activity.objects.filter(pk=inst.pk).update(meeting_url=generated_url)
            inst.meeting_url = generated_url
        external_emails = form.cleaned_data.get("external_participants") or []
        participant_emails = list(
            inst.participants.exclude(email="").values_list("email", flat=True)
        )
        all_recipients = list(dict.fromkeys(participant_emails + external_emails))
        if all_recipients:
            inst.start_datetime = inst.start_datetime or form.cleaned_data.get(
                "start_datetime"
            )
            inst.end_datetime = inst.end_datetime or form.cleaned_data.get(
                "end_datetime"
            )
            bridge = SimpleNamespace(request=self.request)
            MeetingsCreateForm._send_invites(bridge, inst, all_recipients)

    def _is_calendar_request(self):
        """Return True when the request originates from the calendar page."""
        referer = (
            self.request.META.get("HTTP_HX_CURRENT_URL")
            or self.request.META.get("HTTP_REFERER")
            or ""
        )
        return "calendar-view" in referer

    def get_object_or_error_response(self, request):
        """
        Override to return the calendar-aware reload script when the
        activity pk is not found, instead of the generic reloadButton response.
        """
        obj, error_response = super().get_object_or_error_response(request)
        if error_response is not None and self._is_calendar_request():
            error_response = HttpResponse(
                "<script>$('#reloadMainContent').click();closeModal();</script>"
            )
        return obj, error_response

    def form_valid(self, form):
        """
        Handle form submission and save the activity.
        """
        is_meeting = form.cleaned_data.get("activity_type") == "meeting"
        if is_meeting:
            self._prepare_meeting_activity(form)
        if self._is_calendar_request():
            self.return_response = HttpResponse(
                "<script>$('#reloadMainContent').click();closeModal();</script>"
            )
        else:
            self.return_response = HttpResponse(
                "<script>$('#reloadButton').click();closeModal();</script>"
            )
        response = super().form_valid(form)
        if is_meeting:
            self._after_meeting_activity_save(form)
        return response
