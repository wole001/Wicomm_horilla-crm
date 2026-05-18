# Misc template tags (`horilla_generics/templatetags/horilla_tags/misc_tags.py`)

## Purpose

`misc_tags.py` contains small generic tags that do not fit other specialized tag modules.

Currently it provides one utility tag:

- `get_user_model_meta`

This tag exposes user-model identity metadata for templates that need app/model names dynamically.

---

## Registered tag

## `get_user_model_meta` (simple_tag)

Returns a dictionary describing the `User` model from `horilla.auth.models`.

Returned keys:

- `app_label`: `User._meta.app_label`
- `model_name`: `User._meta.model_name` (lowercase model identifier)
- `model_class_name`: `User.__name__` (class name, e.g. `User`)

Example return shape:

```python
{
  "app_label": "auth",
  "model_name": "user",
  "model_class_name": "User",
}
```

---

## Template usage

Load tags:

```django
{% load horilla_tags %}
```

Assign metadata:

```django
{% get_user_model_meta as user_meta %}
```

Use values:

```django
data-app="{{ user_meta.app_label }}"
data-model="{{ user_meta.model_name }}"
data-class="{{ user_meta.model_class_name }}"
```

This is useful when building dynamic URLs, data attributes, or generic helper components requiring model identifiers.

---

## Typical use cases

- passing user model app/model info into frontend scripts
- dynamic generic components that operate on model metadata
- constructing query params or hidden fields for generic helper endpoints

---

## Design notes

- The tag reads model metadata from imported `User` model directly (not from settings-based runtime lookup).
- Because output is static metadata, there is no request/user dependency in this tag.
- The result is lightweight and safe for repeated template usage.

---

## Caveats

- If project user model strategy changes from `horilla.auth.models.User`, this tag must be updated accordingly.
- Key names are fixed; template code should rely on exactly:
  - `app_label`
  - `model_name`
  - `model_class_name`

---

## Summary

`misc_tags.py` currently provides a focused metadata helper for templates. `get_user_model_meta` exposes consistent user-model identifiers, enabling generic template components to work with model-aware attributes without hardcoding values in template markup.
