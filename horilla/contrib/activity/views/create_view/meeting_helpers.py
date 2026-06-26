"""
Helpers for meeting URL generation and invite email sending.
Used by MeetingsCreateForm and ActivityCreateView (via bridge pattern).
"""

# Standard library imports
import logging

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.branding import load_branding

logger = logging.getLogger(__name__)


def generate_meeting_url(view_self, provider, host, activity):
    """Call the appropriate OAuth API to create a meeting link."""
    title = (
        getattr(activity, "title", None)
        or getattr(activity, "subject", None)
        or "Meeting"
    )
    start = activity.start_datetime
    end = activity.end_datetime
    try:
        if provider == "zoom":
            from horilla.contrib.meeting.models import ZoomOAuthConfig
            from horilla.contrib.meeting.oauth.zoom import create_meeting

            config = ZoomOAuthConfig.objects.filter(user=host).first()
            if not config or not config.is_connected():
                try:
                    from django.contrib import messages

                    messages.error(
                        view_self.request,
                        "Zoom account not connected. Go to My Settings → Meeting to connect.",
                    )
                except Exception:
                    pass
                return ""
            url, error = create_meeting(config, title, start, end)
            if error:
                try:
                    from django.contrib import messages

                    messages.error(view_self.request, f"Zoom: {error}")
                except Exception:
                    pass
            return url or ""

        if provider == "ms_teams":
            from horilla.contrib.meeting.models import MicrosoftTeamsOAuthConfig
            from horilla.contrib.meeting.oauth.teams import create_meeting

            config = MicrosoftTeamsOAuthConfig.objects.filter(user=host).first()
            if not config or not config.is_connected():
                return ""
            url, error = create_meeting(config, title, start, end)
            if error:
                try:
                    from django.contrib import messages

                    messages.error(view_self.request, error)
                except Exception:
                    pass
            return url or ""

        if provider == "google_meet":
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
            if not config or not config.is_connected():
                return ""
            session = _get_oauth_session(config)
            _start = start or _dt.now(_tz.utc)
            _end = end or (_start + _td(hours=1))

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
            api_url = (
                f"{GOOGLE_CALENDAR_API_BASE}/calendars/{PRIMARY_CALENDAR_ID}"
                f"/events?conferenceDataVersion=1"
            )
            resp = session.post(api_url, json=body)
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
                del_url = (
                    f"{GOOGLE_CALENDAR_API_BASE}/calendars/{PRIMARY_CALENDAR_ID}"
                    f"/events/{google_event_id}"
                )
                session.delete(del_url)
            return meet_url

    except Exception as exc:
        logger.exception(
            "Meeting URL generation failed for provider=%s: %s", provider, exc
        )
        try:
            from django.contrib import messages

            messages.error(view_self.request, f"Failed to generate meeting link: {exc}")
        except Exception:
            pass
    return ""


def send_meeting_invites(view_self, activity, emails):
    """Send an HTML meeting invitation via the configured outgoing mail server."""
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives, get_connection

    if not emails:
        return

    mail_config = None
    try:
        from horilla.contrib.mail.models import HorillaMailConfiguration

        company = getattr(view_self.request.user, "company", None)
        mail_config = (
            HorillaMailConfiguration.objects.filter(
                company=company, mail_channel="outgoing", is_primary=True
            ).first()
            or HorillaMailConfiguration.objects.filter(
                mail_channel="outgoing", is_primary=True
            ).first()
            or HorillaMailConfiguration.objects.filter(mail_channel="outgoing").first()
        )
    except Exception:
        pass

    title = activity.title or activity.subject or "Meeting"
    meeting_url = activity.meeting_url or ""
    start = activity.start_datetime
    end = activity.end_datetime
    host_user = activity.meeting_host or view_self.request.user
    host_name = str(host_user)

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

    company = getattr(view_self.request, "active_company", None) or getattr(
        view_self.request.user, "company", None
    )
    company_name = str(company) if company else str(load_branding()["TITLE"])

    template_context = {
        "activity": activity,
        "title": title,
        "meeting_url": meeting_url,
        "host_name": host_name,
        "time_line": time_line,
        "company_name": company_name,
    }

    mail_template = getattr(activity, "mail_template", None)
    subject_line = f"Meeting Invitation: {title}"
    if mail_template:
        try:
            rendered = mail_template.render_subject(context=template_context)
            if rendered:
                subject_line = rendered
        except Exception:
            pass
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
    {f'<p style="margin:6px 0;font-size:14px;color:#333">&#128279; <strong>Join Link:</strong> <a href="{meeting_url}" style="color:#e54f38;">{meeting_url}</a></p>' if meeting_url else ""}
  </div>

  {f'<div style="text-align:center;margin-top:25px"><a href="{meeting_url}" style="display:inline-block;padding:10px 20px;background-color:#e54f38;color:white;text-decoration:none;border-radius:6px;font-weight:500;margin:5px">Join Meeting</a></div>' if meeting_url else ""}

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
            get_connection("horilla.contrib.mail.backends.HorillaDefaultMailBackend")
            if mail_config
            else get_connection()
        )
        msg = EmailMultiAlternatives(
            subject=subject_line,
            body=plain_body,
            from_email=from_email,
            to=emails,
            connection=connection,
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=True)
    except Exception:
        pass
