"""Version information for the horilla mail module."""

# First party imports (Horilla)
from horilla.utils.translation import gettext_lazy as _

__version__ = "1.10.1"
__module_name__ = "Mail"
__release_date__ = ""
__description__ = _(
    "Module for managing incoming and outgoing emails through mail servers and Outlook."
)
__icon__ = "assets/icons/icon1.svg"

__1_10_1__ = _(
    "Mail forms aligned with HorillaModelForm / ModelForm layout: field_order, "
    'Meta.fields = "__all__", Meta.exclude, and keep_on_form on configuration forms.'
)

__1_10_0__ = _(
    "Release 1.10: mail ships under the contrib package tree with Django app label mail. "
    "Imports, API routes, URLs, permissions, templates, and static asset paths "
    "updated to drop the legacy prefixed mail app name."
)

__1_1_2__ = _(
    "Improved mail template standardization, async mail handling with "
    "background thread execution, and enhanced notification and mail "
    "action separation for approval workflows."
)

__1_1_1__ = _(
    "Minor compatibility improvements and internal stability updates "
    "to align with the enhanced generics framework and visualization system."
)
__1_1_0__ = _(
    "Migrated from Django AppConfig to Horilla AppLauncher and and replaced"
    "Django utilities with horilla.utils.decorators, horilla.utils.translation, and horilla.shortcuts where applicable."
)
