"""Module containing package metadata used by Horilla (version, name, icons)."""

from django.utils.translation import gettext_lazy as _

__version__ = "1.11.0"
__module_name__ = _("Core System")
__release_date__ = ""
__description__ = _(
    "Core system providing authentication, configuration, utilities, and platform-level services."
)
__icon__ = "assets/icons/logo.png"

__1_11_0__ = _(
    "Workflow automation engine (rules, conditions, actions, Celery time triggers, "
    "execution history). Public booking platform with slots, public pages, reminders, "
    "and lead/contact/activity integration. ERP-style _inherit model extensions with "
    "InjectField and extension-owned migrations. ShiftHour scheduling and BusinessHour "
    "enhancements with holiday support. HTMX-first UX, multi-step form refactors, "
    "django-countries subdivisions, permission inheritance fixes, activity/booking mail "
    "templates, and Django 6.0 generics stability improvements."
)

__1_10_1__ = _(
    "Meeting Integration contrib app (Zoom/Teams OAuth, meeting links, activity hooks). "
    "Generics export and JSONField display improvements. My Profile panel scrolls within "
    "a fixed viewport. Calendar Google settings respect active company on POST. "
    "Scheduled automations use corrected Celery task paths."
)

__1_10_0__ = _(
    "Major platform 1.10 layout: support apps consolidated under the contrib namespace with "
    "short Django app labels (activity, core, mail, theme, and related modules). "
    "AppLauncher configs, imports, URL namespaces, static paths, and permission "
    "or content-type strings updated to match the new labels. "
    "Added sync tooling to align migration records, content types, audit "
    "log references, and related data when upgrading existing databases."
)


__1_9_0__ = _(
    "Added Google Calendar integration with sync, service, and settings support. "
    "Implemented cadence signals for runtime activities. Centralized HorillaView "
    "layout resolution with get_layout_url() for backend-driven layout selection."
)


__1_8_1__ = _(
    "Switched Channels backend from InMemoryChannelLayer to RedisChannelLayer. "
    "Moved Holiday model to dedicated holidays.py. Improved branch list layout, "
    "business hour and holiday bulk select, and viewport-based table heights. "
    "Added SECURITY.md documentation."
)


__1_8_0__ = _(
    "Introduced unified Process Builder system combining reviews and approvals. "
    "Added async notification and mail handling with background thread execution. "
    "Improved health check endpoint and version changelog modal system. "
    "Updated assign_first_company_to_all_users signal to use User model directly."
)


__1_7_0__ = _(
    "Strengthened core validation with strict enforcement of include_models during "
    "feature registration, validation of subsection-to-section mappings, and export "
    "of StreamingHttpResponse via Horilla HTTP utilities."
)


__1_6_0__ = _(
    "Added health check endpoint, synced fiscal year and period logic, "
    "improved version changelog modal system, and switched Django Channels "
    "backend to Redis for better performance and reliability."
)


__1_5_0__ = _(
    "Improved global search model registry loading, standardized error handling "
    "with dedicated 403, 404, 405, and 500 templates, strengthened authentication "
    "flow using Django authenticate(), and applied multiple security and "
    "stability improvements across internal views."
)


__1_4_0__ = _(
    "Introduced the Horilla AppLauncher system for dynamic application "
    "registration. Added horilla.shortcuts, horilla.urls, and horilla.utils "
    "utilities. Refactored project URL handling and improved internal "
    "framework architecture for modular applications."
)


__1_2_0__ = _(
    "Improved system configuration handling, strengthened dashboard layout "
    "validation, enhanced filter processing reliability, and added multiple "
    "defensive validation improvements across core components."
)


__1_1_0__ = _(
    "Added an 'All Companies' option to the company dropdown, allowing users "
    "to view data irrespective of company selection."
)
