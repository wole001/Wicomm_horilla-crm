# Form class mixin (`horilla_generics/forms/form_class_mixin.py`)

## Purpose

`form_class_mixin.py` defines shared form-class behavior used by both:

- `HorillaModelForm` (single-step)
- `HorillaMultiStepForm` (wizard/multi-step)

It centralizes:

- field-permission based field removal
- readonly enforcement at clean-time (anti-tampering)
- reusable widget attribute builders (Select2/date/time/etc.)

This avoids duplication and keeps permission/widget behavior consistent across form types.

---

## Constants for consistent widget styling

Module-level CSS constants:

- `WIDGET_INPUT_CSS_CLASS`
- `WIDGET_INPUT_CSS_CLASS_NO_PR`
- `WIDGET_TIME_CSS_CLASS`
- `SELECT_READONLY_CLASS_SUFFIX`

These ensure single-step and multi-step forms render inputs/selects with unified visual style.

---

## `HorillaFormMixin`

Main shared mixin class.

Responsibilities:

- remove fields according to `field_permissions`
- preserve mandatory fields in create/duplicate mode
- enforce readonly constraints in cleaned data
- build standardized attrs for select2/date/datetime/time widgets

Expected form attributes:

- `field_permissions` mapping (`field -> readwrite|readonly|hidden`)
- `instance`
- optional `duplicate_mode`
- `self._meta.model`

---

## Permission-driven field removal

## `_remove_fields_by_permission(...)`

Arguments:

- `skip_field_names=()`
- `duplicate_mode=False`
- `skip_hidden_widget=False`

Behavior:

1. exits early if no `field_permissions`,
2. determines mode:
   - create (`instance` missing pk)
   - duplicate (from form attr or argument),
3. iterates current form fields,
4. skips protected names and optionally hidden widgets,
5. applies rules:
   - `hidden`:
     - remove in edit mode
     - in create/duplicate, remove only if not mandatory
   - `readonly` in create/duplicate:
     - remove only if not mandatory
6. deletes accumulated fields.

Why important:

- hidden/readonly permissions should not remove required inputs in create/duplicate flows.

---

## Mandatory field detection

## `_is_field_mandatory(field_name, field)`

Checks if field is required by model schema:

- mandatory when model field has `null=False` and `blank=False`

Fallback:

- uses `field._original_required` or `field.required`.

Used by permission-removal and readonly decisions.

---

## Readonly enforcement in `clean()`

## `_enforce_readonly_in_cleaned_data(cleaned_data)`

Server-side safety check for edit mode.

Runs only when:

- `field_permissions` present
- editing existing instance (`instance.pk`)

Flow per readonly field:

1. resolve model field type
2. compute original value from instance:
   - M2M -> list of related objects
   - FK/scalar -> attribute
3. compare original vs submitted using type-aware logic:
   - M2M by pk set
   - FK by related pk
   - scalar by direct value
4. if changed:
   - restore original value in `cleaned_data`
   - add `ValidationError(code="readonly_field")`
5. if unchanged:
   - still normalize cleaned value back to original

This prevents client-side tampering from bypassing readonly UI.

---

## Select/FK/M2M permission helpers

## `_should_disable_select_for_permission(field_name, model_field)`

Returns whether select-like widget should be disabled for readonly permissions.

Logic:

- only applies when permission is `readonly`
- in create/duplicate mode:
  - mandatory fields remain enabled
- otherwise disabled

Used when deciding widget interactivity for FK/M2M/select controls.

---

## `_apply_readonly_to_select_attrs(attrs)`

Mutates attrs for readonly select appearance:

- adds `disabled` + `data-disabled`
- appends readonly visual class suffix:
  - `bg-gray-100 cursor-not-allowed opacity-60`

Provides consistent readonly style for select widgets.

---

## Select2 attribute builders

## `_build_select2_m2m_attrs(...)`

Builds attrs for M2M select2 widget with pagination.

Includes:

- `data-url` -> `horilla_generics:model_select2`
- placeholder text from model verbose name
- `multiple=true`
- `data-initial` as comma-joined selected IDs
- `data-field-name`, `id`, `data-form-class`
- optional `data-object-id`
- optional `data-parent-model` for runtime `DynamicForm`

Used by form classes to initialize M2M select widgets uniformly.

---

## `_build_select2_fk_attrs(...)`

FK counterpart of M2M builder.

Differences:

- no `multiple`
- `data-initial` is single selected ID string
- same endpoint/metadata conventions as M2M builder

---

## Date/time widget attribute builders

## `_build_datetime_widget_attrs(existing_attrs=None, readonly=False)`

Returns attrs for `datetime-local` input:

- `type=datetime-local`
- shared no-right-padding input class
- optional `readonly`

## `_build_date_widget_attrs(existing_attrs=None, readonly=False)`

Returns attrs for `date` input:

- `type=date`
- shared no-right-padding class
- optional `readonly`

## `_build_time_widget_attrs(existing_attrs=None, readonly=False, extra_style=None)`

Returns attrs for `time` input:

- `type=time`
- time-specific CSS class
- optional extra inline style (icon spacing etc.)
- optional `readonly`

These builders standardize widget attrs and reduce repeated widget setup code.

---

## Integration in form classes

`HorillaModelForm` and `HorillaMultiStepForm` typically use this mixin to:

- remove disallowed fields early,
- enforce readonly integrity during cleaning,
- apply unified attrs on dynamic FK/M2M/date/time widgets.

Typical pattern:

1. initialize fields and permissions
2. call `_remove_fields_by_permission(...)`
3. build/assign widget attrs via builder helpers
4. in `clean()`, call `_enforce_readonly_in_cleaned_data(cleaned_data)`

---

## Practical example (conceptual)

```python
class MyForm(HorillaFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.field_permissions = kwargs.pop("field_permissions", {})
        super().__init__(*args, **kwargs)
        self._remove_fields_by_permission(
            skip_field_names=("condition_fields",),
            duplicate_mode=kwargs.get("duplicate_mode", False),
        )

    def clean(self):
        cleaned = super().clean()
        self._enforce_readonly_in_cleaned_data(cleaned)
        return cleaned
```

---

## Caveats

- readonly enforcement runs only in edit mode; create/duplicate rely on field removal/visibility decisions.
- M2M/FK comparison logic assumes submitted cleaned values are model instances (typical Django behavior).
- `data-parent-model` is added only for class name `DynamicForm`; custom dynamic class names may need override.
- widget class constants are global; project-specific theme changes may require updating these shared strings.

---

## Summary

`form_class_mixin.py` is the shared policy and widget utility layer for Horilla forms. It enforces field-permission behavior consistently, protects readonly fields from tampering, and standardizes complex widget attribute construction across single-step and multi-step form implementations.
