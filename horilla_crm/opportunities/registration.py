"""
Feature registration for Opportunities app.
"""

# First party imports (Horilla)
from horilla.contrib.cadences.registration import register_cadence_tab
from horilla.registry.feature import register_model_for_feature

register_model_for_feature(
    app_label="opportunities",
    model_name="OpportunityStage",
    features=["import_data", "export_data", "global_search"],
)

register_model_for_feature(
    app_label="opportunities",
    model_name="Opportunity",
    all=True,
    features=["approval_models", "reviews_models", "scoring", "workflow_models"],
)

register_model_for_feature(
    app_label="opportunities", model_name="OpportunityTeam", features=["global_search"]
)

register_model_for_feature(
    app_label="opportunities",
    model_name="OpportunitySplit",
    features=["report_choices"],
)

register_cadence_tab(
    app_label="opportunities",
    model_name="Opportunity",
    url_prefix="opportunity-cadences-tab/<int:pk>/",
    url_name="opportunity_cadences_tab",
)
