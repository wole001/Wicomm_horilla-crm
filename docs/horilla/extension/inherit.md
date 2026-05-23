# Horilla `_inherit` — Model Extension Guide

Extend existing Horilla models with new database columns **without** modifying core app migrations.

## Quick start

```python
# my_lead_extensions/models.py
from horilla.db import models
from horilla.contrib.core.models import HorillaCoreModel


class LeadExtension(HorillaCoreModel):
    _inherit = "leads.Lead"

    industry_code = models.CharField(max_length=20, null=True, blank=True)
```

```python
# my_lead_extensions/apps.py
from horilla.apps import AppLauncher
from horilla.utils.translation import gettext_lazy as _


class MyLeadExtensionsConfig(AppLauncher):
    name = "my_lead_extensions"
    verbose_name = _("Lead Extensions")
    auto_import_modules = ["models"]
```

```python
# local_settings.py
INSTALLED_APPS += ["my_lead_extensions"]  # after horilla_crm.leads
```

```bash
python manage.py makemigrations my_lead_extensions
python manage.py migrate
```

Migrations are written to **your app only** — `leads/migrations/` should not receive extension-owned DDL.

### NOT NULL columns on tables that already have rows

If you add a non-nullable field **without** `null=True`, **without** `db_default=`, and **without** a model-level `default=`, Django must choose a **temporary default** for existing rows when you run `makemigrations`. The stock autodetector does this via `MigrationQuestioner.ask_not_null_addition` (interactive prompts, or a default in non-interactive mode).

**Earlier Horilla builds** skipped that step for `InjectField`, so `makemigrations` looked fine but `migrate` failed with `NOT NULL constraint failed` on SQLite/Postgres. **`HorillaAutodetector` now mirrors Django’s `_generate_added_field` logic** for injected fields (including `preserve_default` and the questioner calls).

Until you regenerate migrations with that fix, you can still avoid the error by defining the field as nullable or with an explicit default, for example:

```python
industry_name = models.CharField(max_length=100, default="", blank=True)  # or null=True, blank=True
```

**`unique=True`** on a new NOT NULL column with a **single** placeholder default (e.g. `""`) is unsafe if you already have multiple leads — Django may still let you proceed, but the DB will reject duplicate empty values. Prefer `null=True, blank=True` first, backfill, then add uniqueness in a later migration.

### AlterField → extension app (`AlterInjectedField`)

The first migration for a new column uses **`InjectField`** (`_generate_added_field`). Later edits (`verbose_name`, `help_text`, `max_length`, etc.) produce Django’s **`AlterField`**. That path calls `add_operation("leads", AlterField(...))` on the **target** app by default.

**`HorillaAutodetector`** now intercepts **`AlterField`** / **`RemoveField`** in `add_operation` and rewrites them to **`AlterInjectedField`** / **`RemoveInjectedField`** under the owning extension app when the field is in **`INJECTION_MAP`**.

If you already created **`horilla_crm/leads/migrations/0003_alter_lead_industry_code.py`** and it was **never applied**, delete that file and run `makemigrations` again so the alter lives only under **`my_lead_extensions`**. If **0003 was applied**, coordinate a proper revert/fake strategy before cleaning history.

### Removing an injected column

**`RemoveField`** becomes **`RemoveInjectedField`** in the extension app when the column is injected. Ownership is resolved from **`INJECTION_MAP`** or from existing **`InjectField`** operations on disk (so you can comment out the field and run `makemigrations` safely).

**Never** let Django create `leads/migrations/000X_remove_lead_<injected_field>.py` — that `RemoveField` runs against the wrong migration state and breaks `migrate … zero` with `KeyError: '<field>'`. Delete any such core-app migration and regenerate under your extension app only.

## Rules

| Topic | Rule |
|-------|------|
| Base class | `HorillaCoreModel` |
| `_inherit` format | `"app_label.ModelName"` e.g. `"leads.Lead"` — **ModelName may use Django class casing**; the metaclass registers lazy ops with `model_name.lower()` to match Django’s `(app_label, model_name)` registry keys |
| `clean()` | Do not call `super().clean()`; target `clean()` runs first |
| App order | Extension apps **after** apps they extend in `INSTALLED_APPS` |
| Removal | `python manage.py migrate my_lead_extensions zero` then uninstall app |

## Implementation package

```text
horilla/extension/
├── registry.py       # INJECTION_MAP
├── migration_ops.py  # InjectField, AlterInjectedField, RemoveInjectedField
├── autodetect.py     # HorillaAutodetector
└── metaclass.py      # ExtensionModelBase (on HorillaCoreModel)
```

The metaclass treats Horilla fields (`from horilla.db import models`) as Django `Field` subclasses — use normal model fields on extension classes.

## Bootstrap

Migration autodetector patching runs when **`horilla.contrib.core`** finishes loading (`CoreConfig.ready()`). Do not import `horilla.extension` from `horilla/__init__.py` or you may see `AppRegistryNotReady` during `manage.py` startup.

See [Plan_HORILLA_INHERIT_MIGRATION.md](../../Plan_HORILLA_INHERIT_MIGRATION.md) §4.5 for architecture details.
