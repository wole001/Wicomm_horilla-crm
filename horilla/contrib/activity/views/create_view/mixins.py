"""
Shared permission-checking mixin for activity create/update form views.
"""

from horilla.apps import apps
from horilla.db import models
from horilla.shortcuts import get_object_or_404, render
from horilla.web import Http404, HttpResponse

from ...models import Activity


class ActivityOwnerPermissionMixin:
    """
    Mixin that gates GET requests on owner-field membership or the
    ``activity.add_activity`` / ``activity.change_activity`` permissions.

    Subclasses must set ``model = Activity`` and define ``get()``.
    Call ``_check_owner_permission(request, object_id, model_name, app_label, pk)``
    and return the result immediately if it is not ``None``.
    """

    def _check_owner_permission(self, request, object_id, model_name, app_label, pk):
        """
        Return an HttpResponse if access is denied, or None to continue.

        Logic:
        - If object_id + model_name are provided, verify the user owns (via
          OWNER_FIELDS) or has add_activity permission on the parent object.
        - If only pk is provided (edit path), verify the user owns the activity
          or has change_activity permission.
        - Otherwise, deny with a 403 render.
        """
        if object_id and model_name:
            try:
                model_class = apps.get_model(app_label=app_label, model_name=model_name)
                try:
                    instance = get_object_or_404(model_class, pk=object_id)
                except Http404:
                    from django.contrib import messages

                    messages.error(
                        request,
                        f"{self.model._meta.verbose_name.title()} not found or no longer exists.",
                    )
                    return HttpResponse(
                        "<script>$('#reloadButton').click();closeModal();</script>"
                    )

                owner_fields = getattr(model_class, "OWNER_FIELDS", ["owner"])
                user_is_owner = False
                for field in owner_fields:
                    if hasattr(instance, field):
                        value = getattr(instance, field)
                        if isinstance(value, models.Model):
                            if value.id == request.user.id:
                                user_is_owner = True
                                break
                        elif hasattr(value, "all"):
                            if request.user in value.all():
                                user_is_owner = True
                                break

                if not user_is_owner and not request.user.has_perm(
                    "activity.add_activity"
                ):
                    return render(request, "403.html")

                return None  # access granted

            except LookupError:
                return render(request, "403.html")

        if pk:
            if Activity.objects.filter(
                owner_id=request.user, pk=pk
            ).first() or request.user.has_perm("activity.change_activity"):
                return None  # access granted
            return None  # original code fell through to super() here too

        return render(request, "403.html")
