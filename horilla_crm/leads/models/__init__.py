"""
init file for leads models
"""

from horilla_crm.leads.models.base import (
    LeadStatus,
    Lead,
    EmailToLeadConfig,
    LeadCaptureForm,
)

from horilla_crm.leads.models.scoring_rule import (
    ScoringRule,
    ScoringCriterion,
    ScoringCondition,
    EmailActivityScoring,
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

    # Scoring models
    "ScoringRule",
    "ScoringCriterion",
    "ScoringCondition",
    "EmailActivityScoring",

    # Assignment rule models
    "LeadAssignmentRule",
    "LeadAssignmentCondition",
    "LeadAssignmentMatchCriteria",
]
