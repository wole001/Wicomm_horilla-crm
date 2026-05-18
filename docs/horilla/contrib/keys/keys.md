# Horilla Keys app — deep dive (`horilla.contrib.keys`)

## What this app does

- **`ShortcutKey`** persistence: per-user keybinding to navigate to a path or named URL (modifier + key).
- Ships **`keys/assets/js/short_key.js`** via `AppLauncher.js_files` so the browser listens for shortcuts globally.
- **Bootstraps default shortcuts** for every new **`User`** in `signals.py` (`post_save`, `created=True`).
- **REST API** at `keys/` for CRUD on user shortcuts from settings UI.

---

## App startup (`apps.py`)

`KeysConfig`:

| Setting | Value |
|---------|--------|
| `name` | `horilla.contrib.keys` |
| `label` | `keys` |
| `verbose_name` | Keyboard Shortcuts |
| `js_files` | `keys/assets/js/short_key.js` |
| `url_prefix` | `shortkeys/` |
| `url_namespace` | `keys` |
| `auto_import_modules` | `menu`, `signals` |
| API | `keys/` → `horilla.contrib.keys.api.urls` |

Note: HTTP paths use **`shortkeys/`** while API pattern is `keys/`—do not confuse when reverse-engineering routes.

---

## Signals (`signals.py`) — default shortcut matrix

### `DEFAULT_SHORTCUTS`

Static list of `{page, key, command}` entries always inserted for a new user—for example:

- `/` + `H` + `alt`
- `/my-profile-view/` + `P` + `alt`
- `/shortkeys/short-key-view/` + `K` + `alt`
- …

### `OPTIONAL_APP_SHORTCUTS`

Entries may specify:

- **`app`** — if that string is **not** in `INSTALLED_APPS`, the shortcut is skipped (keeps optional contrib apps from breaking URL reverse).
- **`url_name`** — resolved with `reverse_lazy` to populate `page`, or explicit **`page`** path.

Examples in code: dashboard (`D`), reports (`R`), calendar (`I`), activity (`Y`).

### `create_all_default_shortcuts`

- `@receiver(post_save, sender=User)` — only when **`created`**.
- Bulk-creates **`ShortcutKey`** rows after merging predefined + optional lists (`_resolve_shortcut_page`).

For uniqueness rules and conflict handling, see [default_shortcut_registration.md](default_shortcut_registration.md).

---

## Menu (`menu.py`)

Registers **My Settings** or **Settings** entry for the shortcut editor (`short-key-view` path). Exact HTMX attributes live in `menu.py`.

---

## Models (`models.py`)

Read **`ShortcutKey`** for:

- FK to user, stored path, key character, modifier (`alt`, `ctrl`, …), active flag, ordering.

---

## Typical flows

1. New employee account created → defaults inserted → JS hotkey navigates immediately.
2. User opens **Keyboard shortcuts** settings → HTMX table bound to API → PATCH updates row.
3. Optional app uninstalled → optional shortcuts skipped at user creation time.

---

## Related documentation

- Step-by-step extension guide for other apps: [default_shortcut_registration.md](default_shortcut_registration.md)
