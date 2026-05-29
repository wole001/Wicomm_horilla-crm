# Booking App

The `booking` app provides a public-facing, multi-step scheduling system. Visitors book meetings via a
shareable URL without logging in. Hosts manage their booking pages and incoming bookings from within
the CRM.

---

## App Configuration

```python
# booking/apps.py
class BookingConfig(AppLauncher):
    name              = "booking"
    verbose_name      = _("Booking")
    url_prefix        = "booking/"
    url_module        = "booking.urls"
    url_namespace     = "booking"
    auto_import_modules = ["registration", "signals", "menu"]
    celery_schedule_module   = "celery_schedules"
    celery_schedule_variable = "HORILLA_BEAT_SCHEDULE"
```

---

## Models

### `BookingPage`

A public booking calendar owned by a host user.

| Field | Type | Notes |
|---|---|---|
| `slug` | `SlugField` | Unique URL identifier — used in `/book/<slug>/` |
| `title` | `CharField` | Display name shown on the booking page |
| `description` | `TextField` | Optional details shown to visitors |
| `host` | FK → `AUTH_USER_MODEL` | Owner; also the `OWNER_FIELDS` entry |
| `participants` | M2M → `AUTH_USER_MODEL` | Added to every meeting created from this page |
| `business_hour` | FK → `core.BusinessHour` | Governs available weekdays and hours |
| `shift_hour` | FK → `core.ShiftHour` | Alternative to `business_hour` for shift-based schedules |
| `duration` | `PositiveIntegerField` | Slot length in minutes (default 30) |
| `buffer_before` / `buffer_after` | `PositiveIntegerField` | Gap before/after each slot in minutes |
| `advance_notice` | `PositiveIntegerField` | Minimum minutes before a slot can be booked (default 60) |
| `booking_window` | `PositiveIntegerField` | Days into the future visitors may book (default 30) |
| `max_per_day` | `PositiveIntegerField` | Daily booking cap; `NULL` = unlimited |
| `is_online` | `BooleanField` | Enables meeting provider selection |
| `meeting_provider` | `CharField` | `zoom`, `google_meet`, or `ms_teams` |
| `location` | `CharField` | Physical address for in-person meetings |
| `questions` | `JSONField` | Custom questions asked at step 3 of the booking form |
| `reminder_hours` | `PositiveIntegerField` | Hours before meeting to send reminder; `NULL` = disabled |
| `allow_reschedule` | `BooleanField` | Enables public reschedule link (default `True`) |
| `reschedule_cutoff_days` | `PositiveIntegerField` | Prevent reschedule within X days of meeting (default 1) |
| `allow_cancel` | `BooleanField` | Enables public cancel link (default `True`) |
| `cancel_cutoff_days` | `PositiveIntegerField` | Prevent cancellation within X days of meeting (default 1) |
| `primary_color` | `CharField` | Hex brand color injected as CSS variable `--brand` (default `#e54f38`) |
| `confirmation_mail_template` | FK → `mail.HorillaMailTemplate` | Overrides default confirmation email |
| `cancellation_mail_template` | FK → `mail.HorillaMailTemplate` | Overrides default cancellation email |
| `reschedule_mail_template` | FK → `mail.HorillaMailTemplate` | Overrides default reschedule email |

`OWNER_FIELDS = ["host"]` — row-level access is scoped to the host.

### `Booking`

An individual booking submitted by a visitor.

| Field | Type | Notes |
|---|---|---|
| `booking_page` | FK → `BookingPage` | Parent page |
| `booker_name` | `CharField` | Visitor's name |
| `booker_email` | `EmailField` | Visitor's email |
| `start_datetime` | `DateTimeField` | Meeting start (timezone-aware) |
| `end_datetime` | `DateTimeField` | Meeting end (timezone-aware) |
| `status` | `CharField` | `pending`, `confirmed`, `cancelled`, `completed`, `no_show` |
| `answers` | `JSONField` | Responses to custom questions |
| `meeting_url` | `URLField` | Video conference join link |
| `cancellation_token` | `UUIDField` | Unguessable token used in cancel/reschedule links |
| `cancellation_reason` | `TextField` | Optional reason supplied when cancelling |
| `activity` | OneToOne → `activity.Activity` | Meeting activity created on booking confirmation |

Database indexes are on `(booking_page, start_datetime)`, `booker_email`, and `status`.

---

## Slot Availability (`booking/utils.py`)

`get_available_slots(page, target_date)` returns a list of available `time` objects.

**Rules applied in order:**

1. `target_date` must be within `page.booking_window` days from today.
2. Page must have a linked `BusinessHour` or `ShiftHour`.
3. Weekday must be a working day (not closed, not a holiday).
4. Slots are generated from day `start_time` to `end_time` in steps of `duration + buffer_after` minutes.
5. Slots earlier than `now + advance_notice` minutes are skipped.
6. Slots overlapping existing `pending` or `confirmed` bookings are skipped.
7. If `max_per_day` is set, at most that many slots are returned.

`_get_day_hours(bh, day_code)` resolves working hours from either a `BusinessHour` (supporting
`24_7`, `24_5`, and `custom` types with same/different timing) or a `ShiftHour`.

---

## Public Booking Form (`booking/templates/public/booking_form.html`)

A standalone, login-free, three-step form rendered for visitors.

### Steps

| Step | Label | Content |
|---|---|---|
| 1 | Select Date | Horizontal date-strip carousel |
| 2 | Select Time | Grid of available time slots fetched via `AvailableSlotView` |
| 3 | Your Details | Name, email, and any custom questions |

### Date Strip (`renderDateStrip`)

The date carousel shows 6 date cards at a time. Navigation arrows shift the window forward or
backward through the current month. The month header updates as the window moves.

**Date display** — each card renders the weekday abbreviation, day number, and month abbreviation
using values read directly from the JavaScript `Date` object:

```js
card.innerHTML =
    `<div class="dc-day">${WEEKDAY_SHORT[d.getDay()]}</div>` +
    `<div class="dc-num">${d.getDate()}</div>` +
    `<div class="dc-mon">${MONTH_NAMES[d.getMonth()].slice(0,3)}</div>`;
```

`d.getDate()` and `d.getMonth()` are used rather than the raw loop index. This is important because
JavaScript's `Date` constructor automatically overflows day values beyond the end of the month (e.g.
`new Date(2026, 4, 32)` resolves to June 1). Using the loop index directly would display invalid
dates such as "May 32" at the end of a month. Reading back from the `Date` object always shows the
correct, real date.

### Slot Loading

When a date card is clicked, `loadSlots(iso)` sends a `fetch` request to `AvailableSlotView`
(`/book/<slug>/slots/?date=YYYY-MM-DD`) and renders the returned slots as clickable time buttons.
Slots are filtered server-side using `get_available_slots`.

### Timezone

The visitor's timezone is detected automatically via `Intl.DateTimeFormat` and sent to the server
with each slot request. The server converts it to the page host's company timezone for slot
calculation.

---

## URL Patterns (`booking/urls.py`, `app_name = "booking"`)

### Authenticated (Host) Views

| URL | Name | View |
|---|---|---|
| `booking/booking-settings/` | `booking_settings` | `BookingSettingsView` |
| `booking/booking-page-nav/` | `booking_page_nav` | `BookingPageNavView` |
| `booking/booking-page-list/` | `booking_page_list` | `BookingPageListView` |
| `booking/booking-page-create/` | `booking_page_create` | `BookingPageCreateView` |
| `booking/booking-page-edit/<pk>/` | `booking_page_edit` | `BookingPageCreateView` |
| `booking/booking-page-delete/<pk>/` | `booking_page_delete` | `BookingPageDeleteView` |
| `booking/booking-availability/<pk>/` | `booking_availability` | `BookingAvailabilityView` |
| `booking/booking-embed/<pk>/` | `booking_embed` | `BookingEmbedView` |
| `booking/booking-page-detail/<pk>/` | `booking_page_detail` | `BookingPageDetailView` |
| `booking/booking-list/<pk>/` | `booking_list` | `BookingListView` |
| `booking/my-bookings/` | `my_bookings` | `MyBookingsView` |
| `booking/booking-status/<pk>/` | `booking_status` | `BookingStatusUpdateView` |

### Public (No Login) Views

| URL | Name | View |
|---|---|---|
| `booking/book/<slug>/` | `public_booking` | `PublicBookingView` |
| `booking/book/<slug>/slots/` | `available_slots` | `AvailableSlotView` |
| `booking/book/cancel/<uuid:token>/` | `booking_cancel` | `PublicBookingCancelView` |
| `booking/book/reschedule/<uuid:token>/` | `booking_reschedule` | `PublicBookingRescheduleView` |

---

## Signal

```python
# booking/signals.py
from django.dispatch import Signal

booking_submitted = Signal()
```

Fired by `PublicBookingView` after the `Booking` record is saved.

**Keyword arguments:**

| Argument | Type | Description |
|---|---|---|
| `booker_name` | `str` | Full name entered by the visitor |
| `booker_email` | `str` | Email entered by the visitor |
| `booking_instance` | `Booking` | The newly created `Booking` object |
| `company` | `Company \| None` | Company derived from the `BookingPage` |

Receivers in `horilla_crm.leads` create a `Lead`, `Contact`, and `Activity` from this signal.

---

## Email Notifications (`booking/tasks.py`)

Three functions send transactional emails. All use `HorillaMailConfiguration` for SMTP routing
(falls back to `DEFAULT_FROM_EMAIL`).

| Function | Trigger | Template override field |
|---|---|---|
| `send_booking_confirmation_email` | Booking created | `confirmation_mail_template` |
| `send_status_change_email` | Host updates status | `cancellation_mail_template` / `reschedule_mail_template` |
| `send_booking_reminders` (Celery task) | Every 15 minutes via Beat | — |

### Reminder Celery Task

```python
# booking/celery_schedules.py
HORILLA_BEAT_SCHEDULE = {
    "send-booking-reminders-every-15min": {
        "task": "booking.tasks.send_booking_reminders",
        "schedule": timedelta(minutes=15),
    },
}
```

The task finds bookings whose `reminder_at` (`start_datetime - reminder_hours`) falls within the
current 15-minute window and sends an HTML reminder email to the booker.

---

## `BookingPage` Helper Methods

| Method | Returns |
|---|---|
| `get_public_url(request=None)` | Absolute or relative URL of the public booking form |
| `get_edit_url()` | URL for `booking_page_edit` |
| `get_delete_url()` | URL for `booking_page_delete` |
| `get_availability_url()` | URL for `booking_availability` |
| `get_embed_url()` | URL for `booking_embed` |
| `get_detail_url()` | URL for `booking_page_detail` |
