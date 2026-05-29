# Horilla `_inherit_form` — Form Extension Plan

> **Status:** Design / implementation plan (not yet shipped)
> **Companion:** [inherit.md](./inherit.md) (model `_inherit`)
> **Parent form:** `horilla.contrib.generics.forms.HorillaModelForm` (`single_step.py`)
> **Reference child:** `horilla_crm.leads.forms.LeadSingleForm(OwnerQuerysetMixin, HorillaModelForm)`

---

## 1. Executive summary

Horilla CRM already allows **model** extension via `_inherit = "leads.Lead"` without editing core migrations. **Forms are still closed:** each view sets `form_class = LeadSingleForm`, and all layout/validation logic lives in core `horilla_crm/*/forms.py`.

This plan defines **`_inherit_form`**: extension apps declare a **placeholder form class** that extends a **specific existing form** (by dotted import path). At startup, Horilla **composes** a new concrete form class (same MRO rules as normal Python) and views resolve it through **`resolve_form_class()`**.

| Goal | Mechanism |
|------|-----------|
| Add fields / widgets / validators | Declared `forms.Field` on extension + model `_inherit` columns |
| Adjust `Meta` (`exclude`, `keep_on_form`, `widgets`) | Merged inner `Meta` on composed class |
| Customize layout | `field_order`, `step_fields`, view kwargs |
| Hook lifecycle | `__init__`, `clean`, `clean_<field>` chained via MRO |
| No core edits | Extension app only; `get_form_class()` resolves composed class |

**No database migrations** are involved (unlike model `_inherit`).

---

## 2. Problem statement

### 2.1 How forms work today

**Parent (framework):**

```text
HorillaFormMixin          # __init_subclass__: merges HORILLA_FORM_EXCLUDE into Meta.exclude
    └── HorillaModelForm  # single-step: widgets, permissions, conditions, clean()
```

Defined in:

- `horilla/contrib/generics/forms/form_class_mixin.py` — `HorillaFormMixin`
- `horilla/contrib/generics/forms/single_step.py` — `HorillaModelForm` (lines 31–591)
- `horilla/contrib/generics/forms/multi_step.py` — `HorillaMultiStepForm`

**Child (module app):**

```python
class LeadSingleForm(OwnerQuerysetMixin, HorillaModelForm):
    field_order = [...]
    class Meta:
        model = Lead
        fields = "__all__"
        exclude = ["lead_score"]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # queryset, HTMX country/state, etc.
```

**View binding:**

```python
class LeadCreateView(HorillaSingleFormView):
    form_class = LeadSingleForm  # bound at import time
```

`HorillaSingleFormView.get_form_class()` (`single_form.py` ~131–135) returns `self.form_class` unchanged when set. It only builds a dynamic form when `form_class is None`.

### 2.2 Why model `_inherit` alone is not enough

| Need | Model `_inherit` | Form extension |
|------|------------------|----------------|
| DB column | Yes | N/A |
| Widget / HTMX attrs | No | Yes (`__init__`) |
| `field_order` / step placement | No | Yes |
| `Meta.exclude` per form | No | Yes |
| `clean_<field>` form-level rules | Model `clean` only | Yes |
| `OwnerQuerysetMixin` behavior | N/A | Must keep MRO |

Injected model fields with `Meta.fields = "__all__"` may appear on the form **after** the model is patched, but **order, widgets, HTMX, and per-form exclude** remain core-owned unless we add `_inherit_form`.

### 2.3 Failure mode if we only patch modules

Replacing `horilla_crm.leads.forms.LeadSingleForm` after views import **does not update** views that already did:

```python
from horilla_crm.leads.forms import LeadSingleForm
form_class = LeadSingleForm  # stale reference
```

**Resolution must happen in `get_form_class()`**, not only by mutating the forms module.

---

## 3. Design principles

1. **Target the concrete child form**, not `HorillaModelForm` globally.
   Extensions attach to `"horilla_crm.leads.forms.LeadSingleForm"`, preserving `OwnerQuerysetMixin` and all `LeadSingleForm.__init__` logic.

2. **Composition over replacement.**
   `ComposedLeadSingleForm = compose(LeadSingleForm, [Ext1, Ext2])` with bases `(LeadSingleForm, ExtMixin2, ExtMixin1)` — extensions after target in MRO so `super().__init__` chains correctly.

3. **Same app ordering rule as models.**
   Extension apps listed **after** the app that owns the target form in `INSTALLED_APPS`.

4. **Pair with model `_inherit`.**
   Column on `leads.Lead` via `my_lead_extensions.models`; form UX via `my_lead_extensions.forms`.

5. **Bootstrap from `CoreConfig.ready()`** — never `horilla/__init__.py` (same as model extensions).

---

## 4. Public API for extension developers

### 4.1 Syntax

```python
# my_lead_extensions/forms.py
from django import forms
from horilla.extension.forms import HorillaFormExtension  # placeholder base
from horilla.urls import reverse_lazy


class LeadSingleFormExtension(HorillaFormExtension):
    """
    Extends the CRM Lead single-step create/edit form.
    Requires model: _inherit = "leads.Lead" for industry_code column.
    """
    _inherit_form = "horilla_crm.leads.forms.LeadSingleForm"

    # --- Optional: explicit form field (overrides ModelForm default for widget/label) ---
    # industry_code = forms.CharField(required=False, ...)

    # --- Layout (CRM convention; merged by composer) ---
    field_order_insert = [
        ("industry", "industry_code"),  # insert industry_code after industry
    ]

    class Meta:
        # Merged into LeadSingleForm.Meta (see §5.3)
        exclude = ()  # extra excludes only; core audit fields still via HorillaFormMixin
        # keep_on_form = ()
        # widgets = {}
        # labels = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "industry_code" in self.fields:
            self.fields["industry_code"].widget.attrs.update(
                {"class": "uppercase", "placeholder": "e.g. FIN"}
            )

    def clean_industry_code(self):
        code = self.cleaned_data.get("industry_code")
        if code:
            return code.upper()
        return code
```

### 4.2 `_inherit_form` format

| Rule | Value |
|------|--------|
| Format | `"<python_module>.<ClassName>"` |
| Example | `"horilla_crm.leads.forms.LeadSingleForm"` |
| Invalid | `"leads.Lead"`, `"LeadSingleForm"` without module |
| Multi-step | `"horilla_crm.leads.forms.LeadFormClass"` |

Validation at import: module importable, class exists, class is subclass of `django.forms.Form` (typically `HorillaModelForm` / `HorillaMultiStepForm`).

### 4.3 Extension class base: `HorillaFormExtension`

Placeholder base with **`ExtensionFormBase` metaclass** (mirror `ExtensionModelBase`):

- When `_inherit_form` is set: register contributions, return lightweight placeholder (no `ModelForm` instantiation).
- When not set: raise — extensions must declare a target.

Extension classes **must not** subclass `LeadSingleForm` directly (that would require importing core forms at extension import time and creates circular app dependencies).

### 4.4 App configuration

```python
# my_lead_extensions/apps.py
class MyLeadExtensionsConfig(AppLauncher):
    name = "my_lead_extensions"
    auto_import_modules = ["models", "forms"]  # forms required
```

```python
# settings — extension AFTER horilla_crm.leads
INSTALLED_APPS += ["my_lead_extensions"]
```

---

## 5. Composition specification

### 5.1 Registry

```python
# horilla/extension/forms/registry.py
FORM_EXTENSION_REGISTRY: dict[str, list[ExtensionSpec]] = {}
# key: "horilla_crm.leads.forms.LeadSingleForm"
# value: ordered list of extension specs (INSTALLED_APPS order)
```

`ExtensionSpec` holds: `class_name`, `module`, `declared_fields`, `meta_attrs`, `class_attrs`, `methods`, `inherit_form` path.

### 5.2 Composed class shape

For target `T` and extensions `[E1, E2]`:

```python
def compose_form_class(target: type[Form]) -> type[Form]:
    mixins = [_spec_to_mixin(spec) for spec in extensions_for(target)]
    name = f"{target.__name__}Extended"
    meta = _merge_meta(target, mixins)
    namespace = _merge_namespace(target, mixins)
    namespace["Meta"] = meta
    return type(name, (target, *reversed(mixins)), namespace)
```

**MRO example:**

```text
ComposedLeadSingleForm
  → LeadSingleFormExtensionMixin (E2)
  → LeadOtherExtensionMixin (E1)
  → LeadSingleForm
  → OwnerQuerysetMixin
  → HorillaModelForm
  → HorillaFormMixin
  → ModelForm
  → ...
```

Extension `__init__` / `clean_*` use `super()` → runs target `LeadSingleForm.__init__` → `HorillaModelForm.__init__` (full widget pipeline in §6).

### 5.3 `Meta` merge rules

| Attribute | Merge policy |
|-----------|----------------|
| `model` | **Target wins** (required; extension must not change model) |
| `fields` | Target wins; if extension adds **declared-only** fields not on model, append to `fields` list |
| `exclude` | **Union** (target + all extensions + `HorillaFormMixin` base exclude still via `__init_subclass__` on composed class) |
| `keep_on_form` | **Union** |
| `widgets` | **Dict merge** (extension keys override target) |
| `labels` | **Dict merge** (extension overrides) |
| `help_texts` | **Dict merge** |
| `error_messages` | **Dict merge** per field |

`HorillaFormMixin.__init_subclass__` runs on the **composed** class and still applies `HORILLA_FORM_EXCLUDE` to the merged `Meta.exclude`.

### 5.4 Class-level attributes

| Attribute | Used by | Merge policy |
|-----------|---------|----------------|
| `field_order` | CRM forms (layout convention) | See §5.5 |
| `field_order_insert` | Extension API | List of `(after_field, new_field)` tuples |
| `field_order_append` | Extension API | Fields appended if not in order |
| `step_fields` | `HorillaMultiStepForm` | Per-step **list extend** (§5.6) |
| `step_fields_insert` | Extension API | `{step: [(after, field), ...]}` |
| `condition_fields` | View + form kwargs | Union (rare on child forms) |
| `hidden_fields` | View passes kwargs | Not on class — view-level only |

**Note:** `field_order` is defined on CRM child forms but is not referenced in `horilla/contrib/generics` templates in the current tree; the composer still merges it for CRM/JS conventions and future template support.

### 5.5 `field_order` algorithms

**Option A — append (default):**

```python
merged = list(target.field_order) + [
    f for f in ext.field_order_append
    if f not in target.field_order
]
```

**Option B — insert (recommended for extensions):**

```python
for after, new_field in ext.field_order_insert:
    if new_field not in merged:
        idx = merged.index(after) + 1 if after in merged else len(merged)
        merged.insert(idx, new_field)
```

**Conflict:** two extensions insert at same index → `INSTALLED_APPS` order wins (later extension inserts later).

### 5.6 `step_fields` (multi-step)

Target example (`LeadFormClass`):

```python
step_fields = {1: [...], 2: ["lead_company", ...], 3: [...], 4: [...]}
```

Extension:

```python
step_fields_insert = {2: [("industry", "industry_code")]}
# or
step_fields_append = {2: ["industry_code"]}
```

Merge: copy target dict → apply inserts/appends per step. `HorillaMultiStepForm.__init__` already assigns unlisted `__all__` fields to last step — composed class keeps that behavior.

### 5.7 Declared `forms.Field` on extension

| Case | Behavior |
|------|----------|
| Field exists on model (injected via `_inherit`) | Extension may omit declaration; ModelForm builds from model. Extension declaration **overrides** widget/label/required |
| Field only on extension class | Must be on model too for `ModelForm` save — **document: form-only fields unsupported** unless model `_inherit` added |
| Same name as target redeclaration | Extension wins (prefer override via `__init__` widget attrs) |

### 5.8 Method chaining

**Correct base order:** `(Target, ExtN, ..., Ext1)` so `Ext1.__init__` calls `super()` → … → `Target.__init__` → `HorillaModelForm.__init__`.

| `clean` | `Target.clean` → `HorillaModelForm.clean` (permissions, conditions) — extensions should use `clean_<field>` instead of overriding `clean` |
| `clean_<field>` | MRO: call `super().clean_<field>()` in extensions |

**Rule for extension authors:** Prefer `clean_<field>` and `__init__` with `super()`; avoid overriding `clean()` unless chaining `super().clean()`.

### 5.9 `clean()` exception (difference from model `_inherit`)

| Model extension | Form extension |
|-----------------|----------------|
| Do **not** call `super().clean()` on extension model class | Form extensions **should** call `super().__init__()` and `super().clean_<field>()` |

Model rule does not apply to forms — forms use normal Python MRO.

---

## 6. Preserving `HorillaModelForm` behavior

The composed class must still run the parent pipeline in `HorillaModelForm.__init__` (`single_step.py`):

| Step | What it does | Extension impact |
|------|----------------|------------------|
| `_pop_form_options` | `request`, `field_permissions`, `condition_*`, `hidden_fields`, `duplicate_mode` | Pass-through kwargs from view unchanged |
| `ModelForm.__init__` | Builds fields from `Meta` + model | Injected model fields included when `fields="__all__"` |
| `_setup_file_and_initial` | File/image initial attrs | Extensions run after via `super().__init__` |
| Condition fields | `add_condition_fields`, HTMX | Only if view passes `condition_fields` |
| Field loop | Widget CSS, select2, date/time, readonly | Runs **before** extension `__init__` body — extension `__init__` can tweak attrs after |
| `_remove_fields_by_permission` | 4-layer field permissions | Extension fields subject to same permissions if on model |

`HorillaModelForm.clean()` (~426–499):

- FK/M2M permission checks via `_get_fresh_queryset` (uses `self.request`)
- `_enforce_readonly_in_cleaned_data`
- `clean_condition_fields`

Extension `clean_<field>` runs as part of `ModelForm.full_clean()` **before** `clean()` — document ordering for extension authors.

**`OwnerQuerysetMixin`:** Stays on target form (`LeadSingleForm`). Composed class inherits it through `LeadSingleForm` — extensions must not break MRO.

---

## 7. Resolution API

### 7.1 `resolve_form_class(form_class)`

```python
# horilla/extension/forms/resolve.py
_CACHE: dict[type, type] = {}

def resolve_form_class(form_class: type | str) -> type:
    if isinstance(form_class, str):
        form_class = _import_form_class(form_class)
    if form_class in _CACHE:
        return _CACHE[form_class]
    composed = FORM_COMPOSED_MAP.get(_form_path(form_class))
    result = composed if composed else form_class
    _CACHE[form_class] = result
    return result
```

`FORM_COMPOSED_MAP` populated in `apply_form_extensions()` during `CoreConfig.ready()`.

### 7.2 View integration (required)

**`HorillaSingleFormView.get_form_class`:**

```python
def get_form_class(self):
    base = super().get_form_class()  # existing dynamic-form branch
    if base is None:
        return base
    from horilla.extension.forms.resolve import resolve_form_class
    return resolve_form_class(base)
```

**`HorillaMultiStepFormView.get_form_class`:** same pattern.

**Custom CRM views** that override `get_form_class` must call `resolve_form_class` or use resolved class.

### 7.3 Select2 / user picker / `data-form-class`

`HorillaModelForm._build_select2_*_attrs` sets:

```python
"data-form-class": f"{self.__module__}.{self.__class__.__name__}"
```

After composition, use stable registry key on composed class:

```python
__horilla_form_path__ = "horilla_crm.leads.forms.LeadSingleForm"
```

Select2 allowlist (`select2.py`) must accept original path, composed path, or resolve before instantiate.

### 7.4 `form_valid` / duplicate check / automations

Any code using `form.__class__` for permissions should see the composed class; registry key remains the **target** path for stable hooks.

---

## 8. Package layout

```text
horilla/extension/forms/
├── __init__.py          # export resolve_form_class, HorillaFormExtension
├── registry.py          # FORM_EXTENSION_REGISTRY, register_extension()
├── metaclass.py         # ExtensionFormBase
├── compose.py           # compose_form_class(), merge helpers
├── resolve.py           # resolve_form_class(), cache
└── bootstrap.py         # apply_form_extensions() — called from CoreConfig.ready()

horilla/extension/tests/
└── test_form_extension.py
```

Update `horilla/contrib/core/apps.py`:

```python
def ready(self):
    ...
    from horilla.extension.forms.bootstrap import apply_form_extensions
    apply_form_extensions()
```

---

## 9. End-to-end example: `industry_code`

### 9.1 Model (existing)

```python
# my_lead_extensions/models.py
class LeadExtension(HorillaCoreModel):
    _inherit = "leads.Lead"
    industry_code = models.CharField(max_length=20, null=True, blank=True, unique=True)
```

### 9.2 Single-step form extension

```python
# my_lead_extensions/forms.py
class LeadSingleFormExtension(HorillaFormExtension):
    _inherit_form = "horilla_crm.leads.forms.LeadSingleForm"
    field_order_insert = [("industry", "industry_code")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "industry_code" in self.fields:
            self.fields["industry_code"].widget.attrs.setdefault(
                "placeholder", "Industry code (e.g. FIN)"
            )
```

### 9.3 Multi-step form extension

```python
class LeadFormClassExtension(HorillaFormExtension):
    _inherit_form = "horilla_crm.leads.forms.LeadFormClass"
    step_fields_insert = {2: [("industry", "industry_code")]}
```

### 9.4 View (unchanged in core)

```python
# horilla_crm/leads/views/lead_actions.py
class LeadCreateView(HorillaSingleFormView):
    form_class = LeadSingleForm  # resolve_form_class applied in get_form_class()
```

---

## 10. Supported extension targets (CRM matrix)

| Target form | Module path | Parent bases | Typical extension needs |
|-------------|-------------|--------------|-------------------------|
| `LeadSingleForm` | `horilla_crm.leads.forms.LeadSingleForm` | `OwnerQuerysetMixin`, `HorillaModelForm` | `field_order_insert`, HTMX widgets |
| `LeadFormClass` | `horilla_crm.leads.forms.LeadFormClass` | `OwnerQuerysetMixin`, `HorillaMultiStepForm` | `step_fields_insert` |
| `ContactSingleForm` | `horilla_crm.contacts.forms.*` | same pattern | country/state HTMX |
| `OpportunitySingleForm` | `horilla_crm.opportunities.forms.*` | same | money fields |
| `AccountSingleForm` | `horilla_crm.accounts.forms.*` | same | — |

**Phase 1 scope:** `HorillaModelForm` and `HorillaMultiStepForm` **child classes only**, not plain `forms.Form` (e.g. `LeadConversionForm`).

---

## 11. Implementation phases

| Phase | Deliverable | Estimate |
|-------|-------------|----------|
| **0** | This document + API review | 0.5 d |
| **1** | `registry`, `metaclass`, `compose`, unit tests (Meta merge, MRO, `step_fields`) | 2 d |
| **2** | `resolve_form_class`, `apply_form_extensions`, `CoreConfig.ready` | 0.5 d |
| **3** | Patch `HorillaSingleFormView` + `HorillaMultiStepFormView` `get_form_class` | 0.5 d |
| **4** | Select2 / user_picker path resolution | 1 d |
| **5** | `my_lead_extensions/forms.py` + manual QA on Lead create/edit | 1 d |
| **6** | `docs/horilla/extension/inherit-forms.md` quickstart + link from `inherit.md` | 0.5 d |
| **7** | Regression: `manage.py check`, existing leads form tests | 1 d |

**Total:** ~7 days (1 developer)

---

## 12. Testing strategy

| Type | Cases |
|------|--------|
| Unit | Invalid `_inherit_form`; duplicate registration; Meta exclude union; `field_order_insert`; `step_fields_insert` |
| Unit | MRO: `super().__init__` calls `HorillaModelForm` widget loop |
| Unit | `resolve_form_class(LeadSingleForm)` returns same class when no extensions |
| Integration | Lead create with `industry_code` visible and saved |
| Integration | Field permission `hidden` on injected field |
| Regression | `LeadSingleForm` country/state HTMX still works after compose |

---

## 13. Risks and limitations

| Risk | Mitigation |
|------|------------|
| Stale `form_class` import in custom views | Document `resolve_form_class`; lint optional |
| Extension overrides `clean()` without `super()` | Breaks permission/condition clean — document |
| Two extensions same field | INSTALLED_APPS order; last wins |
| `forms.Form` subclasses (conversion wizards) | Out of scope phase 1 |
| Dynamic forms (`form_class=None`) | No `_inherit_form` target — use model-only or explicit `form_class` |
| Multi-table / proxy models | Same as ModelForm rules |

### Non-goals (phase 1)

- Template xpath injection (separate future `_inherit_template`)
- List view column extension
- DRF serializer extension
- Extending `HorillaModelForm` globally (all models at once)
- Replacing `OwnerQuerysetMixin` from extensions

---

## 14. Documentation deliverables

| File | Purpose |
|------|---------|
| `docs/horilla/extension/form_extension.md` | This plan |
| `docs/horilla/extension/inherit-forms.md` | Short quickstart (post-implementation) |
| `docs/horilla/extension/inherit.md` | § “Form extensions” linking here |

---

## 15. Comparison: model vs form extension

| | `_inherit` (model) | `_inherit_form` (form) |
|--|-------------------|------------------------|
| Key | `"leads.Lead"` | `"horilla_crm.leads.forms.LeadSingleForm"` |
| Base class | `HorillaCoreModel` | `HorillaFormExtension` |
| Storage | DB + migrations in extension app | Python class composition only |
| Metaclass | `ExtensionModelBase` | `ExtensionFormBase` |
| View change | None | `get_form_class()` must resolve |
| `clean()` | Target first; extension no `super()` | Normal MRO; use `super()` in `__init__` / `clean_<field>` |

---

## 16. Acceptance criteria

- [ ] Extension app can add `industry_code` to Lead single + multi-step UI without editing `horilla_crm/leads/forms.py`
- [ ] `python manage.py check` passes
- [ ] Core `leads` migrations unchanged by form extension
- [ ] `LeadSingleForm` HTMX country/state behavior preserved
- [ ] Removing extension app restores original form (no registry entries)
- [ ] `data-form-class` / select2 still loads correct queryset for FK fields

---

*End of plan — Horilla CRM `_inherit_form` v1.0*
