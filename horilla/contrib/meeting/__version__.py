"""Version and metadata for the horilla.contrib.meeting app."""

from horilla.utils.translation import gettext_lazy as _

__version__ = "1.10.0"
__module_name__ = _("Meeting Integration")
__release_date__ = ""
__description__ = _(
    "Zoom and Microsoft Teams meeting integration with company access control, "
    "OAuth connections, personal meeting URLs, and activity meeting links."
)
__icon__ = "meeting/assets/icons/meetings.svg"

__1_10_0__ = _(
    "Initial release: company-level meeting integration settings, Zoom and Teams OAuth, "
    "per-user provider settings, MeetingLink CRUD, admin integration screens under "
    "Settings → Integrations, My Settings entries, and generate-link support for activities."
)
