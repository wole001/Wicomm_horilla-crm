# Horilla Activity app — deep dive (`horilla.contrib.activity`)

## What this app does

- Central **Activity** model for **events**, **meetings**, **tasks**, and **log calls** in one table (discriminated by `activity_type`).
- Links each row to **any CRM record** via `HorillaContentType` + `object_id` + `GenericForeignKey` (`related_object`), limited by the **`activity_related`** feature registry (see `registration.py`).
- Surfaces in the UI under the **Schedule** sidebar section (sub-section menu) with HTMX navigation into `#mainContent`.
- Exposes a **REST API** under `/activity/` for external clients.

---

## App startup (`apps.py`)

`ActivityConfig` (`AppLauncher`):

| Setting | Value |
|---------|--------|
| `name` | `horilla.contrib.activity` |
| `label` | `activity` |
| `verbose_name` | Activity |
| `url_prefix` | `activity/` |
| `url_module` | `horilla.contrib.activity.urls` |
| `url_namespace` | `activity` |
| `auto_import_modules` | `registration`, `methods`, `menu`, `signals` |

`get_api_paths()` registers `/activity/` → `horilla.contrib.activity.api.urls` (`activity_api`, namespace `activity`).

`signals.py` is imported at startup but currently contains **no receivers** (reserved for future hooks).

---

## Feature registration (`registration.py`)

- **`register_feature("activity_related", "activity_related_models")`** — other apps register models under this key so they appear as valid **related** types for activities (`limit_content_types` on `Activity.content_type`).
- **`register_model_for_feature(..., model_name="Activity", features=["global_search", "automation"])`** — Activities participate in **global search** and can be targets/sources for **automations** (when automation rules reference the activity model).

Without `register_model_for_feature`, the four-layer permission system would not expose standard `activity.*` permissions for `Activity`.

---

## Menu (`menu.py`)

`ActivitySubSection` is registered with `@sub_section_menu.register`:

- **`section`** = `"schedule"` (groups with other schedule apps in the sidebar).
- **`app_label`** = `"activity"` (identity for ordering/placement).
- **`position`** = `2`.
- **`verbose_name`** / **`icon`** — user-visible label and `/assets/icons/activity.svg`.
- **`url`** — `reverse_lazy("activity:activity_view")`.
- **`attrs`** — `MAIN_CONTENT_HX_ATTRS` so list/detail loads via HTMX into the main shell.
- **`perm`** — `["activity.view_activity", "activity.view_own_activity"]` (either permission allows the menu entry; row-level **own** filtering still applies in views via `OWNER_FIELDS`).

---

## Model: `Activity` (`models.py`)

### Base and tenancy

- Extends **`HorillaCoreModel`** (`company`, audit fields, `is_active`, etc.).
- **`OWNER_FIELDS = ["owner", "assigned_to"]`** — enables **view_own_** / **change_own_** style filtering in list views and APIs.

### Polymorphic shape

- **`activity_type`** — `event` | `meeting` | `task` | `log_call`.
- **`status`** — workflow states (`not_started`, `scheduled`, `in_progress`, …); indexed for reporting and list filters.
- **Common fields** — `subject`, `description`, datetimes, `location`, `is_all_day`, M2M **`assigned_to`** / **`participants`**, FK **`meeting_host`**, FK **`owner`**.

### Generic relation

- **`content_type`** → `HorillaContentType`, limited to **`activity_related_models`**.
- **`object_id`** + **`related_object`** — the CRM entity this activity is about (lead, contact, etc.).

### Type-specific columns

- **Task** — `task_priority`, `due_datetime`, `recipient_email`.
- **Log call** — `call_type`, `call_duration_display` / `call_duration_seconds` (auto-derived in `save()` from `HH:MM:SS` string), `call_purpose`, `notes`.
- **Calendar sync** — `google_event_id` (indexed) for Google Calendar integration.

### Indexes

Composite-friendly indexes on `activity_type`, `created_at`, `status`, `start_datetime`, `due_datetime` for list dashboards and calendar views.

### URL helpers

`get_detail_url`, `get_edit_url` (per-type named URLs), `get_activity_edit_url`, `get_delete_url` — used by generics, timeline rows, and mail templates.

### List / inline UI

- **`status_col`** / **`get_status_update_html`** — render partials via `render_template()` for inline status changes in list views.

---

## Typical flows

1. User opens **Activities** from the schedule sub-menu → HTMX loads `activity_view` into the shell.
2. User creates a **task** linked to a **lead** → `content_type`/`object_id` set; `owner`/`assigned_to` drive row permissions.
3. Automations or cadences create **Activity** rows (task/call/email) with due dates → same model, different `activity_type`.
4. Global search indexes activity subjects/titles when the feature registry includes the model.

---

## Related documentation

- Core models and `HorillaContentType`: [../core/models.md](../core/models.md)
- Feature registry: [../core/Registry/feature.md](../core/Registry/feature.md)
- Generics list/detail patterns: [../generics/views/list.md](../generics/views/list.md), [../generics/views/details.md](../generics/views/details.md)
