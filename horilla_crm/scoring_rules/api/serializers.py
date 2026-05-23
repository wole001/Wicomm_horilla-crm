"""Serializers for the scoring_rules app."""

from rest_framework import serializers

from horilla_crm.scoring_rules.models import ScoringCriterion, ScoringRule


class ScoringRuleSerializer(serializers.ModelSerializer):
    """Serializer for ScoringRule model."""

    class Meta:  # pylint: disable=missing-class-docstring
        model = ScoringRule
        fields = "__all__"


class ScoringCriterionSerializer(serializers.ModelSerializer):
    """Serializer for ScoringCriterion model."""

    class Meta:  # pylint: disable=missing-class-docstring
        model = ScoringCriterion
        fields = "__all__"
