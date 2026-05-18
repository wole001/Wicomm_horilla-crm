# Inline edit helpers (`horilla_generics/views/helpers/edit_field.py`)

## Purpose

This module provides HTMX endpoints for **single-field inline editing** in detail views.

It supports the three-step cycle:

1. open editable widget for one field (`EditFieldView`),
2. submit and save (`UpdateFieldView`),
3. cancel edit and restore display mode (`CancelEditView`).

Used directly by `details_tab.html` via `horilla_generics:edit_field`, `cancel_edit`, `update_field`.

---

## Views overview

## 1) `EditFieldView`

```python
class EditFieldView(LoginRequiredMixin, View):
```

- HTMX-only (`@htmx_required`)
- template: `partials/edit_field.html`
- method: `GET`

Route params:

- `pk`
- `field_name`
- `app_label`
- `model_name`

Optional query:

- `pipeline_field` (passed through context)

### What it does

1. resolves model dynamically with `apps.get_model`.
2. fetches object by `pk`.
3. resolves target field from model metadata.
4. computes `field_info` via `get_field_info(...)`.
5. renders edit-widget fragment.

On failure: flashes message and returns reload script.

---

## 2) `UpdateFieldView`

```python
class UpdateFieldView(LoginRequiredMixin, View):
```

- HTMX-only
- template: `partials/field_display.html`
- method: `POST`

Same route params as `EditFieldView`.

### What it does

1. resolves model/object/field.
2. parses submitted value(s) by field type.
3. saves object or m2m relation update.
4. reuses `EditFieldView.get_field_info(...)` to build fresh display context.
5. returns display fragment (non-edit mode).

If parsing/update fails: returns 400 with message.

---

## 3) `CancelEditView`

```python
class CancelEditView(LoginRequiredMixin, View):
```

- HTMX-only
- template: `partials/field_display.html`
- method: `GET`

### What it does

1. resolves model/object/field.
2. calls `EditFieldView.get_field_info(...)` without saving.
3. returns display fragment.

This lets the UI exit edit mode instantly with current stored value.

---

## Field metadata engine (`get_field_info`)

`EditFieldView.get_field_info(field, obj, user)` produces a normalized dict used by both edit and display templates.

Common keys:

- `name`
- `verbose_name`
- `field_type`
- `value`
- `display_value`
- `choices`
- `use_select2`

### Field-type mapping

- `ManyToManyField` -> `select`, `multiple=True`, `use_select2=True`
  - loads currently selected objects as choices.
- `ForeignKey` -> `select`, `use_select2=True`
  - keeps empty option + current selected option.
- choice field -> `select` with all choices + display label from `get_<field>_display`.
- `BooleanField` -> select `Yes/No`.
- `EmailField` -> `email`
- `URLField` -> `url`
- integer types -> `number`
- decimal/float -> `number`, `step=0.01`
- `DateTimeField` -> `datetime-local`
  - converts stored value to user timezone (if `user.time_zone` exists),
  - formats value for input (`YYYY-MM-DDTHH:MM`),
  - formats display with user `date_time_format` if available.
- `DateField` -> `date`, formatted by user `date_format` if available.
- `TextField` -> `textarea`
- fallback -> `text`

---

## Update conversion rules (`UpdateFieldView.post`)

### Many-to-many

- reads `field_name[]` values,
- clears existing relation,
- adds selected IDs (if any).

### ForeignKey

- empty string -> `None`
- otherwise fetch related object by PK.

### Boolean

- empty string -> `None`
- `"True"` -> `True`, else `False`.

### Numbers

- int fields -> `int(value)` or `None`
- decimal -> `Decimal(value)` with explicit invalid handling
- float -> `float(value)` or `None`

### Date/time

- `DateTimeField`:
  - parses ISO datetime from input,
  - interprets in user timezone when available,
  - converts to default timezone for storage.
- `DateField`:
  - parses ISO date and stores date object.

### Other fields

- stored as raw string value.

After update, object is saved and display fragment is returned.

---

## Template interaction

### Trigger (from details tab)

In `details_tab.html`, edit button calls:

```html
hx-get="{% url 'horilla_generics:edit_field' pk=obj.pk field_name=field_name app_label=app_label model_name=model_name %}?pipeline_field={{ pipeline_field }}"
hx-target="#field-{{ field_name }}"
hx-swap="outerHTML"
```

### Edit fragment lifecycle

`partials/edit_field.html` typically contains input + Save/Cancel actions:

- save -> `horilla_generics:update_field` (POST)
- cancel -> `horilla_generics:cancel_edit` (GET)

both target same field container.

---

## Example 1: Basic inline edit (text field)

1. user clicks edit icon on `title`.
2. `EditFieldView` returns text input widget.
3. submit posts `title=New title`.
4. `UpdateFieldView` saves and returns `partials/field_display.html`.
5. row reverts to non-edit mode with updated value.

---

## Example 2: FK field with Select2

Field: `lead_owner` (ForeignKey)

- edit view returns select configured with current owner + Select2 behavior.
- submit posts owner PK.
- update resolves related object and saves FK.
- display shows owner label.

---

## Example 3: datetime field with user timezone

Field: `follow_up_at` (`DateTimeField`)

- edit value is rendered in user timezone as `datetime-local`.
- user changes time and submits.
- backend interprets input in user timezone, converts to default timezone, saves.
- display uses user-configured datetime format if available.

---

## Error handling behavior

- unresolved model/object/field -> reload script response
- invalid decimal/date/datetime -> 400 with descriptive message
- relation lookup failure -> 400

These responses are designed for HTMX fragment flows, not full-page redirects.

---

## Security / permission note

This module assumes calling views/templates gate edit controls (e.g. `can_update`, field permissions in `details_tab.html`).

`EditFieldView/UpdateFieldView` themselves do not perform explicit per-field permission checks beyond authentication; they are intended to be used behind permission-aware UI and URL protection.

---

## Summary

`edit_field.py` is the inline-edit backend for detail tabs: it dynamically builds correct input widgets per field type, safely parses posted values, supports timezone-aware datetime handling, and swaps fragments in/out through HTMX for a smooth edit-save-cancel UX.
