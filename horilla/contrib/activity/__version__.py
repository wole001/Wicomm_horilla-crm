"""Version information for the horilla.contrib.activity module."""

from horilla.utils.translation import gettext_lazy as _

__version__ = "1.10.1"
__module_name__ = "Activity"
__release_date__ = ""
__description__ = _(
    "Module for tracking and managing activities such as tasks,calls, events, and emails."
)
__icon__ = "activity/assets/icons/activity-red.svg"

__1_10_1__ = _(
    "Meeting integration in activities: schedule meetings from activities, send invites "
    "and reminders, and display generated Zoom/Teams meeting links on activity records."
)

__1_10_0__ = _(
    "Release 1.10: activity ships under contrib with app label activity. "
    "AppLauncher, imports, namespaces, registrations, templates, and metadata "
    "references updated from the legacy activity package name to the contrib layout."
)

__1_2_1__ = _(
    "Reduced redundant history entries, improved Many-to-Many field representation, "
    "and added cleaner labels for mail events and activity creation with "
    "new template filters for better rendering."
)

__1_2_0__ = _(
    "Improved activity workflow behavior. The Pending tab now shows all incomplete activities"
    "regardless of status label, and activity type configuration handling was enhanced "
    "for improved workflow accuracy."
)


__1_1_0__ = _(
    "Migrated from Django AppConfig to Horilla AppLauncher and replaced Django utilities with"
    "horilla.utils.decorators, horilla.utils.translation, and horilla.shortcuts where applicable."
)
