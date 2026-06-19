# Horilla Core app — deep dive index (`horilla.contrib.core`)

The **core** app is the largest contrib module: authentication helpers, **multi-company tenancy**, **roles & permissions**, **menus**, **HorillaContentType**, **signals**, **middleware**, **demo data**, and **REST** surface for branches, currencies, users, etc.

This page is an **index and orientation**. Detailed topics live in focused files under `docs/horilla/contrib/core/`.

---

## App startup (`apps.py`)

`CoreConfig` (`AppLauncher`):

| Setting | Value |
|---------|--------|
| `name` | `horilla.contrib.core` |
| `label` | `core` |
| `verbose_name` | Core System |
| `url_prefix` | `""` (empty — routes mount at project root via include) |
| `url_module` | `horilla.contrib.core.urls` |
| `url_namespace` | `core` |
| `auto_import_modules` | `registration`, `signals`, **`scheduler`**, `login_history`, `menu` |
| `celery_schedule_module` | `celery_schedules` |
| `demo_data` | JSON packs: `company.json`, `role.json`, `users.json` with ordering metadata |

`get_api_paths()` exposes multiple `/`-prefixed API includes (read `apps.py` for the authoritative list).

---

## Middleware (high impact)

Registered from **`horilla.contrib.core.middlewares`** in project settings:

- **`TimezoneMiddleware`**, **`ActiveCompanyMiddleware`** — per-request active company + tz.
- **`HorillaExceptionMiddleware`** — maps **`HttpNotFound`** (`horilla.web`) to the custom 404 flow.
- **`Horilla405Middleware`** — when the view returns **405 Method Not Allowed**, renders **`templates/405.html`** (same card layout as other error pages).
- **`SVGSecurityMiddleware`**, **`HTMXRedirectMiddleware`**, **`EnsureSectionMiddleware`** — security + HTMX navigation polish.

Deep behavior belongs next to source; cross-check [settings `base.py`](../../settings/base.md) for middleware order and CSRF settings.

---

## Custom error pages (`templates/` + `views/error_pages.py`)

User-facing errors share **`templates/error.html`** (Tailwind card, dark-mode script). Child templates live at the project **`templates/`** root.

| Template | When it appears | HTTP status |
|----------|-----------------|-------------|
| **`403.html`** | Permission denied (views, decorators, includes with `embed=True`) | 403 |
| **`404.html`** | **`HttpNotFound`** / not found | 404 |
| **`405.html`** | **`Horilla405Middleware`** on disallowed HTTP method | 405 |
| **`csrf_failure.html`** | CSRF verification failed when **`DEBUG=False`** | 403 |

Settings-only embed variant: **`horilla/contrib/core/templates/error/settings_403.html`** (extends the same base).

### CSRF failure (`CSRF_FAILURE_VIEW`)

In **`horilla/settings/base.py`**:

```python
CSRF_FAILURE_VIEW = "horilla.contrib.core.views.error_pages.csrf_failure"
```

Implementation: **`horilla/contrib/core/views/error_pages.py`** → **`csrf_failure(request, reason="")`**.

| `DEBUG` | Behavior |
|---------|----------|
| **`True`** | Delegates to Django’s built-in CSRF failure view (yellow technical help page). |
| **`False`** | Renders **`csrf_failure.html`** with a short user message (`message` context). |

**HTMX POST:** returns **`HX-Redirect`** to `HX-Current-URL`, `Referer`, or `/` so the client reloads and picks up a fresh CSRF token.

**Configuration (common fix):** origin mismatches (e.g. `127.0.0.1` vs `localhost`) require the exact browser origin in **`CSRF_TRUSTED_ORIGINS`** (from `.env`). Example:

```env
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

### Permission 403 vs CSRF 403

Both may return HTTP **403**, but they are different paths:

- **Permission** — view renders **`403.html`** (or modal embed); user lacks access.
- **CSRF** — middleware aborts POST before the view; **`csrf_failure`** runs when **`DEBUG=False`**.

---

## Custom signals (`horilla.contrib.core.signals`)

Platform-wide hooks consumed by theme, currency, login, and installed apps, including:

- **`company_created`** — fired when a new `Company` is created; listeners initialize fiscal year, currency, etc.
- **`company_currency_changed`** — fired after default currency changes; listeners bulk-update `MoneyField` amounts (sent in a background thread so bulk updates do not block the HTTP response)
- **`pre_logout_signal`**, **`pre_login_render_signal`** — theme/login customization
- Product-specific pipeline hooks (e.g. `lead_stage_created`, `opp_stage_created` in `horilla_crm`) connect in their own apps

Theme app listens to **`pre_logout_signal`** / **`pre_login_render_signal`**—see [../theme/theme.md](../theme/theme.md).

---

## Documentation map

| Topic | Doc |
|-------|-----|
| Base models, `HorillaCoreModel`, managers, `HorillaContentType` | [models.md](models.md) |
| Custom `HorillaUser` | [user_model.md](user_model.md) |
| Menus (floating, main, settings, sub-section, my settings) | [Menu/](Menu/floating_menu.md) |
| Registry (features, permissions, assets, limiters) | [Registry/feature.md](Registry/feature.md) |
| URL helpers (`horilla.urls`) | [Urls/urls.md](Urls/urls.md) |
| Web utilities (`horilla.web`) | [web/web.md](../../web/web.md) |
| Decorators (legacy path name) | [Decorator ( Utils )/decorators.md](Decorator%20(%20Utils%20)/decorators.md) |
| Translation shim | [Translation (Utils )/translation.md](Translation%20(Utils%20)/translation.md) |
| Settings / `horilla_apps` / passwords / `CSRF_FAILURE_VIEW` | [settings `base.py`](../../settings/base.md) |
| Exceptions | [Core/exceptions.md](Core/exceptions.md) |
| Keyboard shortcuts registration (core vs keys) | [Shortcuts/shortcuts.md](Shortcuts/shortcuts.md) |
| Shift hours (`ShiftHour` model + form) | [models.md](models.md) · `horilla/contrib/core/forms/shift_hour.py` |

---

## Business hour views (`views/business_hour.py`)

Ten class-based views manage business hour configuration per company.

| View | Base | Purpose |
|------|------|---------|
| `BusinessHourView` | `View` | Shell template; guarded by `@permission_required` |
| `BusinessHourCardView` | `View` | Single company card summary partial |
| `BusinessHourFormView` | `HorillaSingleFormView` | Create/update business hours; blocks duplicate per company |
| `BusinessHourHolidayListView` | `HorillaListView` | Filtered list of holidays for a business hour config |
| `BusinessHourHolidayPanelView` | `View` | Holiday panel partial (HTMX target) |
| `BusinessHourHolidayToggleView` | `View` | HTMX POST — add or remove a holiday record; re-renders panel via `horilla.shortcuts.render` |
| `BusinessHourHolidayModalView` | `View` | Modal listing all holidays for selection |
| `BusinessHourAddHolidayView` | `HorillaSingleFormView` | Modal form to create a new holiday entry |
| `BusinessHourHolidayReadonlyDetailView` | `HolidayDetailView` | Read-only holiday detail opened from the business-hour holiday list (`core:business_hour_holiday_readonly_detail`); `actions = []` |
| `BusinessHourHolidayRemoveView` | `View` | Remove one holiday from a business hour config |

**Duplicate prevention** — `BusinessHourFormView.get()` checks for an existing `BusinessHour` for the active company before rendering; redirects if one exists rather than allowing creation of a second row.

**Performance** — views use `select_related()` / `prefetch_related()` for company and holiday relations to avoid N+1 queries on the card and list pages.

**HTMX return responses** — success handlers call `return_response` containing a script that reloads the detail view panel and shows a Django messages toast; cross-view reloads are orchestrated without full page refreshes.

---

## Shift hour form (`forms/shift_hour.py`)

**`ShiftHourForm`** (`HorillaModelForm`) — create/update named shifts (main hours + two optional breaks + assigned users).

| Pattern | Value |
|---------|--------|
| **`field_order`** | Full list through `assigned_users` (used by **`reorder_shift_hour_form_fields`**, not `Meta.fields`) |
| **`Meta.fields`** | `"__all__"` |
| **`keep_on_form`** | `("company",)` — field stays on form; **`ShiftHourFormView.hidden_fields`** still hides it in the UI |
| **Runtime** | `__init__` adds per-day break `TimeField`s, hides blocks by `timing_type` / `break*_mode`, HTMX reload on toggles |

See [generics single-step `HorillaModelForm`](../generics/forms/single_step.md) for automatic `HORILLA_FORM_EXCLUDE`.

---

## Typical extension tasks

1. **Add a new secured model** — extend `HorillaCoreModel`, add `CompanyFilteredManager`, set `OWNER_FIELDS` / `CURRENCY_FIELDS` as needed, then **`register_model_for_feature`** in your app’s `registration.py`.
2. **Add a settings screen** — `@settings_menu.register` class in your app’s `menu.py` mirroring [Menu/settings_menu.md](Menu/settings_menu.md) patterns.
3. **React to company currency change** — connect receiver to `company_currency_changed` in your `signals.py`.

---

## Related documentation

- Contrib umbrella README: [../README.md](../README.md)
- Cross-app utilities (thread local, queryset helpers): [../utils/utils.md](../utils/utils.md)
