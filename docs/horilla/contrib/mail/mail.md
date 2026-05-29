# Horilla Mail app — deep dive (`horilla.contrib.mail`)

## What this app does

- **Outgoing mail configuration** per channel (SMTP, etc.) via **`HorillaMailConfiguration`**.
- **Message queue / history** via **`HorillaMail`** and **`HorillaMailAttachment`**.
- **Reusable HTML templates** via **`HorillaMailTemplate`** (seeded from `load_template/template.json` on install).
- **Celery** tasks in `tasks.py` for async send; **`scheduler`** module for periodic mail jobs.
- **REST API** at `mail/` for mobile/integrations.

---

## App startup (`apps.py`)

`MailConfig`:

| Setting | Value |
|---------|--------|
| `url_prefix` | `mail/` |
| `url_namespace` | `mail` |
| `auto_import_modules` | `registration`, `signals`, **`scheduler`**, `menu` |
| `celery_schedule_module` | `celery_schedules` |
| `template_files` | `["load_template/template.json"]` |
| API | `mail/` include → `horilla.contrib.mail.api.urls` |

---

## Feature registration (`registration.py`)

```text
register_feature("mail_template", "mail_template_models")
```

Models that expose themselves under **`mail_template_models`** can be selected when building mail templates with merge fields / loops (see mail template editor views).

---

## Models (`models.py`) — concepts

### `HorillaMailConfiguration`

- Stores host, port, username, **`EncryptedCharField`** for **password** and **Outlook client secret**, TLS, default from-address, **`mail_channel`** (`incoming` / `outgoing`) for limit choices on automations.

### `HorillaMail`

- One row per send attempt: headers, body snapshot, status, FK to template used, link to triggering user/company.

### `HorillaMailAttachment`

- File rows bound to a parent mail message (`upload_path` pattern from `horilla.utils.upload`).

### `HorillaMailTemplate`

- Named template with HTML body; referenced by **Automations**, **Cadences**, and manual compose UIs.

---

## Forms (`forms.py`)

### `HorillaMailTemplateForm` (`forms.ModelForm`, not `HorillaModelForm`)

- **`field_order`**: `title`, `subject`, `content_type`, `body`, `company`
- **`Meta.fields = "__all__"`**
- **`Meta.exclude`**: `is_active`, `created_at`, `updated_at`, `created_by`, `updated_by`, `additional_info` — **`company` stays on the form** (manual exclude list, same effect as `keep_on_form` on `HorillaModelForm`)
- Used by **`MailTemplateCreateUpdateView`** (`FormView`, not `HorillaSingleFormView`)

### `SaveAsMailTemplateForm`

- Still uses explicit **`fields = ["title", "body", "company", "content_type"]`** (unchanged)

### Mail configuration (`HorillaModelForm`)

| Form | `keep_on_form` | `Meta.exclude` (high level) |
|------|----------------|----------------------------|
| **`HorillaMailConfigurationForm`** (outgoing SMTP) | `company` | Outlook/OAuth fields (`outlook_*`, `token`, `oauth_state`, `last_refreshed`) |
| **`IncomingHorillaMailConfigurationForm`** | `company` | Outgoing-only SMTP + Outlook/OAuth fields |
| **`OutlookMailConfigurationForm`** | `company` | SMTP fields (`host`, `port`, `from_email`, model `password`, TLS/SSL, …) + token/oauth |

Each configuration form declares a class-level **`password`** or **`outlook_client_secret`** `CharField` override. **`__init__`** required-field logic is unchanged.

### Other

- **`DynamicMailTestForm`**, **`MailTemplateSelectForm`** — plain `forms.Form`; unchanged

---

## Signals (`signals.py`)

Common patterns:

- Update counters or audit when mail delivery status changes.
- Invalidate caches for inbox widgets.

Read `horilla/contrib/mail/signals.py` for concrete `@receiver` blocks.

---

## Scheduler (`scheduler.py`)

Registers APScheduler / Celery beat entries for mailbox sync or retry queues (implementation-specific—read module).

---

## Typical flows

1. Admin configures **outgoing** server → automation picks it via FK or falls back to primary.
2. **HorillaAutomation** with `delivery_channel=mail` renders **`HorillaMailTemplate`** with context from triggering instance → `HorillaMail` row created → Celery sends SMTP.
3. User composes one-off mail from record detail → same models, different view.

---

## Related documentation

- Automations delivery: [../automations/automations.md](../automations/automations.md)
- Notifications (parallel channel): [../notifications/notifications.md](../notifications/notifications.md)
