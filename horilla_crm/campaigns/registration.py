"""
Feature registration for Campaigns app.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_model_for_feature

register_model_for_feature(
    app_label="campaigns",
    model_name="Campaign",
    all=True,
    features=["workflow_models"],
)
