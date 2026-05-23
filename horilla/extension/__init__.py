"""
Horilla _inherit model extension system.

Patches makemigrations and migrate to use HorillaAutodetector so injected fields
generate migrations in extension apps, not in core CRM apps.
"""

from horilla.extension.autodetect import HorillaAutodetector
from horilla.extension.metaclass import (
    EXTENSION_REGISTRY,
    ExtensionModelBase,
)
from horilla.extension.migration_ops import AlterInjectedField, InjectField, RemoveInjectedField
from horilla.extension.registry import INJECTION_MAP

__all__ = [
    "HorillaAutodetector",
    "ExtensionModelBase",
    "EXTENSION_REGISTRY",
    "INJECTION_MAP",
    "InjectField",
    "AlterInjectedField",
    "RemoveInjectedField",
]


def _patch_migration_autodetectors():
    try:
        from django.core.management.commands.makemigrations import (
            Command as MakeMigrationsCommand,
        )
        from django.core.management.commands.migrate import Command as MigrateCommand

        MakeMigrationsCommand.autodetector = HorillaAutodetector
        MigrateCommand.autodetector = HorillaAutodetector
    except ImportError:
        pass


_patch_migration_autodetectors()
