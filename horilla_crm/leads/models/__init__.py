"""
init file for leads models
"""

# Local imports
from horilla_crm.leads.models.base import (
    LeadStatus,
    Lead,
    EmailToLeadConfig,
    LeadCaptureForm,
)


from horilla_crm.leads.models.assignment_rules import (
    LeadAssignmentRule,
    LeadAssignmentCondition,
    LeadAssignmentMatchCriteria,
)

__all__ = [
    # Base models
    "LeadStatus",
    "Lead",
    "EmailToLeadConfig",
    "LeadCaptureForm",
    # Assignment rule models
    "LeadAssignmentRule",
    "LeadAssignmentCondition",
    "LeadAssignmentMatchCriteria",
]
