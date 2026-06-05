"""
Merge detail view class attributes from extension specs onto a target HorillaDetailView.
"""

from __future__ import annotations

from types import SimpleNamespace

from horilla.extension.detail.registry import DetailExtensionSpec
from horilla.extension.list.merge import (
    merge_append_attr,
    merge_columns,
    merge_scalar_overrides,
)

__all__ = [
    "merge_body",
    "merge_header_fields",
    "merge_append_attr",
    "merge_scalar_overrides",
]


def _body_column_specs(specs: list[DetailExtensionSpec]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            columns_insert=spec.body_insert,
            columns_append=spec.body_append,
        )
        for spec in specs
    ]


def _header_column_specs(specs: list[DetailExtensionSpec]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            columns_insert=spec.header_fields_insert,
            columns_append=spec.header_fields_append,
        )
        for spec in specs
    ]


def merge_body(base_body: list | None, specs: list[DetailExtensionSpec]) -> list | None:
    """Apply body_insert / body_append from all specs."""
    return merge_columns(base_body, _body_column_specs(specs))


def merge_header_fields(
    base_header: list | None, specs: list[DetailExtensionSpec]
) -> list | None:
    """Apply header_fields_insert / header_fields_append from all specs."""
    return merge_columns(base_header, _header_column_specs(specs))
