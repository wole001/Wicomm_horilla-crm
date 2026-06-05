"""
Compose concrete Horilla forms with extension mixins (_inherit_form).
"""

from __future__ import annotations

import copy
from types import new_class

from django import forms

from horilla.contrib.generics.forms import HorillaModelForm, HorillaMultiStepForm
from horilla.contrib.generics.forms.form_class_mixin import (
    apply_horilla_form_meta_exclude,
)
from horilla.extension.forms.registry import ExtensionSpec, get_extensions_for


def _import_form_class(path: str) -> type[forms.Form]:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    form_class = getattr(module, class_name)
    if not isinstance(form_class, type) or not issubclass(form_class, forms.BaseForm):
        raise TypeError(f"{path!r} is not a Django BaseForm subclass")
    return form_class


def _union_sequence(*sequences):
    seen = set()
    result = []
    for seq in sequences:
        for item in seq or []:
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result


def _merge_field_order(target: type, specs: list[ExtensionSpec]) -> list | None:
    base_order = list(getattr(target, "field_order", None) or [])
    if not base_order and not any(
        s.field_order_insert or s.field_order_append for s in specs
    ):
        return None

    merged = list(base_order)
    for spec in specs:
        for after, new_field in spec.field_order_insert:
            if new_field in merged:
                continue
            if after in merged:
                merged.insert(merged.index(after) + 1, new_field)
            else:
                merged.append(new_field)
        for new_field in spec.field_order_append:
            if new_field not in merged:
                merged.append(new_field)
    return merged


def _merge_step_fields(target: type, specs: list[ExtensionSpec]) -> dict | None:
    base = getattr(target, "step_fields", None)
    if base is None and not any(
        s.step_fields_insert or s.step_fields_append for s in specs
    ):
        return None

    merged = copy.deepcopy(base) if base else {}

    for spec in specs:
        for step, pairs in (spec.step_fields_insert or {}).items():
            step_list = list(merged.get(step, []))
            for after, new_field in pairs:
                if new_field in step_list:
                    continue
                if after in step_list:
                    step_list.insert(step_list.index(after) + 1, new_field)
                else:
                    step_list.append(new_field)
            merged[step] = step_list
        for step, fields in (spec.step_fields_append or {}).items():
            step_list = list(merged.get(step, []))
            for new_field in fields:
                if new_field not in step_list:
                    step_list.append(new_field)
            merged[step] = step_list
    return merged


def _merge_meta(target: type, specs: list[ExtensionSpec]) -> type | None:
    """Build merged inner Meta class for the composed form."""
    target_meta = getattr(target, "Meta", None)
    if target_meta is None:
        if not specs or not any(s.meta_attrs for s in specs):
            return None
        target_meta = type("Meta", (), {})

    attrs = {}
    for key in ("model", "fields"):
        if hasattr(target_meta, key):
            attrs[key] = getattr(target_meta, key)

    exclude = list(getattr(target_meta, "exclude", None) or [])
    keep_on_form = list(getattr(target_meta, "keep_on_form", None) or [])
    widgets = dict(getattr(target_meta, "widgets", None) or {})
    labels = dict(getattr(target_meta, "labels", None) or {})
    help_texts = dict(getattr(target_meta, "help_texts", None) or {})
    error_messages = dict(getattr(target_meta, "error_messages", None) or {})
    fields_append = []

    for spec in specs:
        meta = spec.meta_attrs
        exclude = _union_sequence(exclude, meta.get("exclude"))
        keep_on_form = _union_sequence(keep_on_form, meta.get("keep_on_form"))
        widgets.update(meta.get("widgets") or {})
        labels.update(meta.get("labels") or {})
        help_texts.update(meta.get("help_texts") or {})
        if meta.get("error_messages"):
            error_messages.update(meta["error_messages"])
        fields_append = _union_sequence(fields_append, meta.get("fields_append"))

    attrs["exclude"] = tuple(exclude) if exclude else ()
    if keep_on_form:
        attrs["keep_on_form"] = tuple(keep_on_form)
    if widgets:
        attrs["widgets"] = widgets
    if labels:
        attrs["labels"] = labels
    if help_texts:
        attrs["help_texts"] = help_texts
    if error_messages:
        attrs["error_messages"] = error_messages

    fields_value = attrs.get("fields")
    if fields_append and fields_value not in (None, "__all__"):
        if isinstance(fields_value, (list, tuple)):
            attrs["fields"] = tuple(_union_sequence(list(fields_value), fields_append))
        else:
            attrs["fields"] = tuple(fields_append)

    return type("Meta", (), attrs)


def _collect_declared_fields(specs: list[ExtensionSpec]) -> dict[str, forms.Field]:
    collected: dict[str, forms.Field] = {}
    for spec in specs:
        for name, field in spec.declared_fields.items():
            if name in collected and name not in spec.override_fields:
                raise ValueError(
                    f"Duplicate declared field {name!r} on {spec.inherit_form} "
                    f"from {spec.module}.{spec.class_name} "
                    f"(already from another extension; use override_fields to allow)"
                )
            collected[name] = field
    return collected


def _spec_to_mixin(spec: ExtensionSpec) -> type:
    """Build a mixin class from an extension spec (methods + declared fields)."""
    namespace = dict(spec.declared_fields)
    for key, value in spec.class_attrs.items():
        if key in (
            "field_order_insert",
            "field_order_append",
            "step_fields_insert",
            "step_fields_append",
        ):
            continue
        namespace[key] = value
    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    mixin = type(mixin_name, (), namespace)

    def __init__(self, *args, **kwargs):
        super(mixin, self).__init__(*args, **kwargs)
        self.setup_form_extension_fields()

    mixin.__init__ = __init__
    return mixin


def compose_form_class(
    target_path: str, target: type[forms.Form] | None = None
) -> type[forms.Form]:
    """
    Compose target form with registered extensions.

    MRO (v1.1): Composed -> ExtN -> ... -> Ext1 -> Target -> ...
    """
    if getattr(target, "__horilla_composed__", False):
        return target

    target = target or _import_form_class(target_path)
    specs = get_extensions_for(target_path)
    if not specs:
        return target

    mixins = [_spec_to_mixin(spec) for spec in specs]
    declared = _collect_declared_fields(specs)

    meta = _merge_meta(target, specs)
    field_order = _merge_field_order(target, specs)
    step_fields = _merge_step_fields(target, specs)

    namespace = dict(declared)
    if meta is not None:
        namespace["Meta"] = meta
    if field_order is not None:
        namespace["field_order"] = field_order
    if step_fields is not None:
        namespace["step_fields"] = step_fields

    composed_name = f"{target.__name__}Extended"
    # v1.1: extensions before target in bases tuple
    bases = tuple(reversed(mixins)) + (target,)

    composed = new_class(
        composed_name,
        bases,
        {},
        lambda ns: ns.update(namespace),
    )

    composed.__horilla_composed__ = True
    composed.__horilla_form_path__ = target_path
    composed.__wrapped_form__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"

    if issubclass(target, (HorillaModelForm, HorillaMultiStepForm)) and hasattr(
        composed, "Meta"
    ):
        apply_horilla_form_meta_exclude(composed.Meta)

    return composed
