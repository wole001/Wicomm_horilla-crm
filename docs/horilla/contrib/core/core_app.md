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
- **`HorillaExceptionMiddleware`**, **`Horilla405Middleware`** — consistent error pages.
- **`SVGSecurityMiddleware`**, **`HTMXRedirectMiddleware`**, **`EnsureSectionMiddleware`** — security + HTMX navigation polish.

Deep behavior belongs next to source; cross-check [Settings/base.md](Settings/base.md) for ordering relative to Django defaults.

---

## Custom signals (`horilla.contrib.core.signals`)

Platform-wide hooks consumed by theme, currency, login, and CRM modules, including:

- `company_created`, `company_currency_changed`
- `pre_logout_signal`, `pre_login_render_signal`
- Pipeline hooks such as `lead_stage_created`, `opp_stage_created` (names per codebase)

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
| HTTP helpers in core package path | [Http/http.md](Http/http.md) |
| Decorators (legacy path name) | [Decorator ( Utils )/decorators.md](Decorator%20(%20Utils%20)/decorators.md) |
| Translation shim | [Translation (Utils )/translation.md](Translation%20(Utils%20)/translation.md) |
| Settings / `horilla_apps` / passwords | [Settings/](Settings/base.md) |
| Exceptions | [Core/exceptions.md](Core/exceptions.md) |
| Keyboard shortcuts registration (core vs keys) | [Shortcuts/shortcuts.md](Shortcuts/shortcuts.md) |
| Shift hours (`ShiftHour` model + form) | [models.md](models.md) · `horilla/contrib/core/forms/shift_hour.py` |

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
