# Horilla Calendar app — deep dive (`horilla.contrib.calendar`)

## What this app does

- **User preferences** for calendar display and sync.
- **Availability** blocks for scheduling.
- **Custom calendars** and **conditions** (org-defined views/filters).
- **Google Calendar** OAuth-style settings and per-user/config rows for sync.
- Exposes **REST API** at `/calendar/` for SPA or integrations.

---

## App startup (`apps.py`)

`CalendarConfig`:

| Setting | Value |
|---------|--------|
| `url_prefix` | `calendar/` |
| `url_namespace` | `calendar` |
| `auto_import_modules` | `registration`, `menu`, `signals` |
| API | `/calendar/` → `horilla.contrib.calendar.api.urls` |

---

## Feature registration (`registration.py`)

- Registers the **`custom_calendar`** feature with registry key **`custom_calendar_models`** (`auto_register_all=False`). Apps opt in models that can participate in custom calendar definitions.

## Menu (`menu.py`)

Registers main / floating entries for the calendar shell view and Google settings (see source for `reverse_lazy` names, icons, and `perm` strings).

---

## Models (`models.py`) — overview

### `UserCalendarPreference`

Per-user defaults: visible calendars, time slot length, week start, sync toggles, etc. (see field definitions in `models.py`).

### `UserAvailability`

Recurring or dated availability windows; used when suggesting meeting times or conflict detection.

### `CustomCalendar` / `CustomCalendarCondition`

Organizations define named calendars and rule rows (similar spirit to report conditions) to filter which activities or events appear.

### `GoogleIntegrationSetting` / `GoogleCalendarConfig`

Store integration credentials/config scopes and mapping between Horilla users and Google calendars. Used by views under `templates/google_calendar/` and sync tasks.

All primary models extend **`HorillaCoreModel`** unless noted otherwise in code—company isolation applies.

---

## Signals (`signals.py`)

Used for:

- Keeping Google tokens refreshed or invalidating on error (check receivers).
- Invalidating caches when preferences change.

(Read `horilla/contrib/calendar/signals.py` for the authoritative list of senders.)

---

## Forms (`forms.py`)

### `CustomCalendarForm` (`HorillaModelForm`)

- **`field_order`**: `name`, `color`, `module`, `start_date_field`, `end_date_field`, `display_name_field`, `is_selected`
- **`Meta.fields = "__all__"`**, **`Meta.exclude = ["user"]`** — `user` is set on create in the view, not on the form
- **`htmx_field_choices_url`**: `generics:get_model_field_choices`
- **`__init__`**: HTMX GET reload merges query params into `initial`; date/display field choices rebuilt from selected `module` (unchanged)

### Other forms

- **`GoogleSyncDirectionForm`** / **`GoogleCredentialsUploadForm`** — plain `forms.Form` / `ModelForm`; not part of the `__all__` refactor

See [single-step form base](../generics/forms/single_step.md) for `HORILLA_FORM_EXCLUDE` on `HorillaModelForm`.

---

## Templates and UX

- Main shell calendar: `horilla/contrib/calendar/templates/calendar.html` (extends project layout; HTMX loads events).
- Google settings partials: `templates/google_calendar/`.

---

## Typical flows

1. User opens **Calendar** from the menu → week/month view loads activities whose datetimes fall in range.
2. User connects **Google** in settings → OAuth flow writes `GoogleCalendarConfig` → sync jobs create/update **`Activity.google_event_id`** rows on the activity app.
3. Mobile or SPA hits **`/calendar/`** API → serializers return JSON blocks consistent with web filters.

---

## Related documentation

- Activity model (events/tasks tied to Google IDs): [../activity/activity.md](../activity/activity.md)
- Dashboard home may embed calendar widgets: [../dashboard/dashboard.md](../dashboard/dashboard.md)
