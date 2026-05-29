"""Version and metadata for the horilla.contrib.workflow app."""

from horilla.utils.translation import gettext_lazy as _

__version__ = "1.10.1"
__module_name__ = _("Workflow")
__release_date__ = ""
__description__ = _(
    "Record-triggered workflow rules with field conditions, immediate actions "
    "(update field, assign task, email, notification), and time-based triggers "
    "scheduled relative to record or rule dates."
)
__icon__ = "assets/icons/automation.svg"

__1_10_1__ = _(
    "WorkflowRuleForm aligned with HorillaModelForm layout: field_order, "
    'Meta.fields = "__all__", and keep_on_form for is_active; action forms unchanged.'
)

__1_10_0__ = _(
    "Initial release: workflow rules per ContentType with create/edit triggers, "
    "AND/OR conditions, ordered immediate actions, time-trigger actions with "
    "Celery scheduling and execution history, Settings → Automations → Workflow Rules, "
    "and integration with registered CRM models via feature registration."
)
