"""
Serializers for horilla_crm.leads models
"""

# Third-party imports (other)
from rest_framework import serializers

# Local imports
from horilla_crm.leads.models import Lead, LeadStatus


class LeadSerializer(serializers.ModelSerializer):
    """Serializer for Lead model"""

    class Meta:
        """Meta options for LeadSerializer."""

        model = Lead
        fields = "__all__"


class LeadStatusSerializer(serializers.ModelSerializer):
    """Serializer for LeadStatus model"""

    class Meta:
        """Meta options for LeadStatusSerializer."""

        model = LeadStatus
        fields = "__all__"
