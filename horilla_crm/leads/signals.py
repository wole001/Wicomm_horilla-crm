"""
Signal handlers for leads in Horilla CRM.
Handles automatic updates when company-related events occur, e.g., currency change.
"""

# Standard library imports
import logging
import threading

# Third-party imports (Django)
from django.db import transaction
from django.db.models.signals import post_migrate, post_save, pre_delete, pre_save
from django.dispatch import Signal, receiver
from django.template import engines

# First-party / Horilla imports
from horilla.apps import apps
from horilla.auth.models import User

# First-party / Horilla apps
from horilla.contrib.core.signals import company_created, company_currency_changed
from horilla.contrib.keys.models import ShortcutKey
from horilla.contrib.notifications.methods import create_notification
from horilla.contrib.utils.middlewares import _thread_local
from horilla.core.exceptions import FieldDoesNotExist
from horilla.db.models import Case, Count, F, IntegerField, Q, When
from horilla.shortcuts import render
from horilla.urls import reverse_lazy
from horilla_crm.leads.models import (
    Lead,
    LeadAssignmentCondition,
    LeadAssignmentRule,
    ScoringCondition,
    ScoringCriterion,
    ScoringRule,
)
from horilla_crm.leads.utils import compute_score

logger = logging.getLogger(__name__)


lead_stage_created = Signal()


@receiver(company_created)
def handle_company_created(sender, instance, request, view, is_new, **kwargs):
    """Inject lead stages loading after company creation"""
    if is_new:  # Only for new companies
        url = reverse_lazy("leads:load_lead_stages", kwargs={"company_id": instance.id})
        response = render(
            request,
            "lead_status/reload_and_load_url_script.html",
            {"load_url": str(url)},
        )
        response["X-Debug"] = "Modal transition in progress"
        return response
    return None


@receiver(company_currency_changed)
def update_crm_on_currency_change(sender, **kwargs):
    """
    Updates Lead amounts when a company's currency changes.
    """
    company = kwargs.get("company")
    conversion_rate = kwargs.get("conversion_rate")

    leads_to_update = []
    leads = (
        Lead.objects.filter(company=company)
        .select_related()
        .only("id", "annual_revenue")
    )

    for lead in leads:
        if lead.annual_revenue is not None:
            lead.annual_revenue = lead.annual_revenue * conversion_rate
            leads_to_update.append(lead)

    if leads_to_update:
        Lead.objects.bulk_update(leads_to_update, ["annual_revenue"], batch_size=1000)


@receiver(post_save, sender=User)
def create_leads_shortcuts(sender, instance, created, **kwargs):
    """Create default keyboard shortcuts for leads when a user is created."""
    predefined = [
        {"page": "crm/leads/leads-view/", "key": "E", "command": "alt"},
    ]

    for item in predefined:
        ShortcutKey.all_objects.get_or_create(
            user=instance,
            key=item["key"],
            command=item["command"],
            defaults={
                "page": item["page"],
                "company": instance.company,
            },
        )


def get_score_field(model):
    """Get the score field name for a given model."""
    score_fields = {
        "lead": "lead_score",
        "opportunity": "opportunity_score",
        "account": "account_score",
        "contact": "contact_score",
    }
    return score_fields.get(model._meta.model_name)


def get_models_for_module(module):
    """
    Dynamically find models matching a module name (e.g., 'lead') across installed apps.
    Only includes models that have a corresponding score field.
    """
    models = []
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            if model._meta.model_name == module:
                score_field = get_score_field(model)
                if score_field and score_field in [f.name for f in model._meta.fields]:
                    models.append(model)
    return models


def build_query_from_conditions(criterion, Model):
    """
    Build a Django ORM query to filter instances that match a criterion's conditions.

    Args:
        criterion: ScoringCriterion instance.
        Model: The Django model class (e.g., Lead).

    Returns:
        Q object representing the combined conditions.
    """
    query = Q()
    for condition in criterion.conditions.all().order_by("order"):
        field = condition.field
        operator = condition.operator
        value = condition.value
        logical_operator = condition.logical_operator

        try:
            Model._meta.get_field(field)
            if operator == "equals":
                if Model._meta.get_field(field).get_internal_type() == "ForeignKey":
                    condition_query = Q(**{f"{field}_id__exact": value})
                else:
                    condition_query = Q(**{f"{field}__exact": value})
            elif operator == "not_equals":
                if Model._meta.get_field(field).get_internal_type() == "ForeignKey":
                    condition_query = ~Q(**{f"{field}_id__exact": value})
                else:
                    condition_query = ~Q(**{f"{field}__exact": value})
            elif operator == "contains":
                condition_query = Q(**{f"{field}__icontains": value})
            elif operator == "not_contains":
                condition_query = ~Q(**{f"{field}__icontains": value})
            elif operator == "starts_with":
                condition_query = Q(**{f"{field}__istartswith": value})
            elif operator == "ends_with":
                condition_query = Q(**{f"{field}__iendswith": value})
            elif operator == "greater_than":
                try:
                    condition_query = Q(**{f"{field}__gt": float(value)})
                except (ValueError, TypeError):
                    condition_query = Q(pk__in=[])
            elif operator == "greater_than_equal":
                try:
                    condition_query = Q(**{f"{field}__gte": float(value)})
                except (ValueError, TypeError):
                    condition_query = Q(pk__in=[])
            elif operator == "less_than":
                try:
                    condition_query = Q(**{f"{field}__lt": float(value)})
                except (ValueError, TypeError):
                    condition_query = Q(pk__in=[])
            elif operator == "less_than_equal":
                try:
                    condition_query = Q(**{f"{field}__lte": float(value)})
                except (ValueError, TypeError):
                    condition_query = Q(pk__in=[])
            elif operator == "is_empty":
                condition_query = Q(**{field: None}) | Q(**{f"{field}__exact": ""})
            elif operator == "is_not_empty":
                condition_query = ~Q(**{field: None}) & ~Q(**{f"{field}__exact": ""})
            else:
                condition_query = Q(pk__in=[])
            if logical_operator == "and":
                query &= condition_query
            else:
                query |= condition_query
        except FieldDoesNotExist:
            logger.warning(
                "Field %s does not exist on %s", field, Model._meta.model_name
            )
            query &= Q(pk__in=[])

    return query


def update_all_scores_for_module(module):
    """
    Update score fields for instances matching active scoring rules' conditions
    using direct database UPDATE queries.

    Args:
        module: String (e.g., 'lead', 'opportunity') indicating the module.
    """
    models = get_models_for_module(module)
    for Model in models:
        score_field = get_score_field(Model)
        if not score_field:
            continue

        with transaction.atomic():
            try:
                Model.objects.update(**{score_field: 0})
                logger.info(
                    "Reset %s to 0 for all %s instances",
                    score_field,
                    Model._meta.model_name,
                )
            except Exception as e:
                logger.error(
                    "Error resetting %s for %s: %s",
                    score_field,
                    Model._meta.model_name,
                    e,
                )
                raise

            rules = ScoringRule.objects.filter(module=module, is_active=True)
            if not rules.exists():
                continue

            for rule in rules:
                for criterion in rule.criteria.all().order_by("order"):
                    query = build_query_from_conditions(criterion, Model)
                    if not query:
                        continue

                    points = criterion.points
                    if criterion.operation_type == "sub":
                        points = -points

                    try:
                        Model.objects.filter(query).update(
                            **{
                                score_field: Case(
                                    When(query, then=F(score_field) + points),
                                    default=F(score_field),
                                    output_field=IntegerField(),
                                )
                            }
                        )
                        logger.info(
                            "Updated %s for %s instances matching criterion %s",
                            score_field,
                            Model._meta.model_name,
                            criterion.id,
                        )
                    except Exception as e:
                        logger.error(
                            "Error updating %s for %s with criterion %s: %s",
                            score_field,
                            Model._meta.model_name,
                            criterion.id,
                            e,
                        )
                        raise


@receiver(post_save, sender=ScoringRule)
@receiver(pre_delete, sender=ScoringRule)
def handle_rule_change(sender, instance, **kwargs):
    """
    Signal handler triggered when a scoring rule is created, updated, or deleted.
    Automatically triggers recalculation of all scores for the associated module.
    """
    update_all_scores_for_module(instance.module)


@receiver(post_save, sender=ScoringCriterion)
@receiver(pre_delete, sender=ScoringCriterion)
def handle_criterion_change(sender, instance, **kwargs):
    """
    Signal handler triggered when a scoring criterion is created, updated, or deleted.
    Ensures scores are recalculated for all modules affected by this criterion.
    """
    update_all_scores_for_module(instance.rule.module)


@receiver(post_save, sender=ScoringCondition)
@receiver(pre_delete, sender=ScoringCondition)
def handle_condition_change(sender, instance, **kwargs):
    """
    Signal handler triggered when a scoring condition is created, updated, or deleted.
    Rebuilds and applies scoring rules to update scores for affected module instances.
    """
    update_all_scores_for_module(instance.criterion.rule.module)


_CRM_SHORTKEY_URL_MIGRATIONS = {
    "/leads/leads-view/": "/crm/leads/leads-view/",
    "/accounts/accounts-view/": "/crm/accounts/accounts-view/",
    "/contacts/contacts-view/": "/crm/contacts/contacts-view/",
    "/opportunities/opportunities-view/": "/crm/opportunities/opportunities-view/",
    "/campaigns/campaign-view/": "/crm/campaigns/campaign-view/",
    "/forecast/forecast-view/": "/crm/forecast/forecast-view/",
}


# Disabled in v1.10.1: this one-time URL migration was only needed for the v1.10.0
# upgrade. Keeping the function in place for v1.10.1 release; remove entirely in the
# next version.
# @receiver(post_migrate, dispatch_uid="migrate_crm_shortkey_urls")
def migrate_crm_shortkey_urls(sender, **kwargs):
    """Prefix existing CRM shortkey URLs with crm/ after the URL restructure."""
    if sender.name != "horilla_crm.leads":
        return
    try:
        for old_url, new_url in _CRM_SHORTKEY_URL_MIGRATIONS.items():
            updated = ShortcutKey.all_objects.filter(page=old_url).update(page=new_url)
            print(f"Migrated {updated} shortkey(s): '{old_url}' → '{new_url}'")
            if updated:
                logger.info(
                    "Migrated %d shortkey(s): '%s' → '%s'", updated, old_url, new_url
                )
    except Exception as exc:
        logger.warning("Could not migrate CRM shortkey URLs: %s", exc)


@receiver(pre_save, sender=Lead)
def update_lead_score(sender, instance, **kwargs):
    """Signal to update lead score before saving a Lead instance."""

    instance.lead_score = compute_score(instance)


def _eval_single_criterion(criteria, lead):
    """
    Evaluate one LeadAssignmentMatchCriteria row against a lead instance.
    Returns True if the criterion matches, False otherwise.
    """
    field = criteria.field
    operator = criteria.operator
    value = criteria.value or ""

    try:
        meta_field = Lead._meta.get_field(field)
    except FieldDoesNotExist:
        logger.warning("Assignment rule: field '%s' does not exist on Lead", field)
        return False

    try:
        raw = getattr(lead, field, None)

        # FK → compare by PK string
        if (
            hasattr(meta_field, "related_model")
            and meta_field.related_model is not None
        ):
            field_val = str(raw.pk) if raw is not None else ""
        else:
            field_val = "" if raw is None else str(raw)

        if operator == "exact":
            return field_val == value
        if operator == "ne":
            return field_val != value
        if operator == "icontains":
            return value.lower() in field_val.lower()
        if operator == "not_contains":
            return value.lower() not in field_val.lower()
        if operator == "istartswith":
            return field_val.lower().startswith(value.lower())
        if operator == "iendswith":
            return field_val.lower().endswith(value.lower())
        if operator == "isnull":
            return not field_val.strip()
        if operator == "isnotnull":
            return bool(field_val.strip())
        if operator in ("gt", "gte", "lt", "lte"):
            try:
                fv, rv = float(field_val), float(value)
                return {"gt": fv > rv, "gte": fv >= rv, "lt": fv < rv, "lte": fv <= rv}[
                    operator
                ]
            except (ValueError, TypeError):
                return False
        if operator == "between":
            parts = [p.strip() for p in value.split(",") if p.strip()]
            if len(parts) == 2:
                try:
                    fv = float(field_val)
                    return float(parts[0]) <= fv <= float(parts[1])
                except (ValueError, TypeError):
                    return False
    except Exception as exc:
        logger.error("Assignment rule criterion eval error (field=%s): %s", field, exc)

    return False


def _eval_condition_criteria(condition, lead):
    """
    Evaluate all match-criteria rows of a condition using their AND/OR logic.
    Returns True if the condition as a whole matches the lead.
    No criteria means "always match".
    """
    criteria_qs = condition.criteria.all().order_by("created_at")
    if not criteria_qs.exists():
        return True
        return True

    result = None
    for criteria in criteria_qs:
        row_result = _eval_single_criterion(criteria, lead)
        if result is None:
            result = row_result
        elif criteria.logical_operator == "or":
            result = result or row_result
        else:
            result = result and row_result

    return bool(result)


def _resolve_target_users(condition):
    """
    Return a queryset of candidate User objects for the condition:
    - 'user' type → the explicitly selected users
    - 'role' type → all users whose role FK matches one of the selected roles
    """
    if condition.assign_to_type == "role":
        roles = condition.assign_to_roles.all()
        return User.objects.filter(role__in=roles, is_active=True)
    return condition.assign_to_users.filter(is_active=True)


def _pick_round_robin(users_qs):
    """
    From a queryset of users, return the one currently owning the fewest active leads.
    Ties broken by PK (lowest first) for determinism.
    """
    if not users_qs.exists():
        return None
    return (
        users_qs.annotate(lead_count=Count("lead")).order_by("lead_count", "pk").first()
    )


def _send_assignment_email(condition, lead, assigned_user):
    """Send assignment email to the assigned user using the condition's mail template."""
    try:
        from django.utils import timezone

        from horilla.contrib.core.models import HorillaContentType
        from horilla.contrib.mail.models import HorillaMail, HorillaMailConfiguration
        from horilla.contrib.mail.services import HorillaMailManager

        tmpl = condition.mail_template
        if not tmpl or not assigned_user.email:
            return

        company = getattr(lead, "company", None)
        sender = None
        if company:
            sender = (
                HorillaMailConfiguration.objects.filter(
                    company=company, mail_channel="outgoing", is_primary=True
                ).first()
                or HorillaMailConfiguration.objects.filter(
                    company=company, mail_channel="outgoing"
                ).first()
            )

        content_type = HorillaContentType.objects.get_for_model(lead)
        mail = HorillaMail.objects.create(
            sender=sender,
            to=assigned_user.email,
            subject=tmpl.subject or "",
            body=tmpl.body or "",
            content_type=content_type,
            object_id=lead.pk,
            mail_status="draft",
            company=company,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        context = {"instance": lead, "user": assigned_user, "lead": lead}

        def _send():
            try:
                if sender:
                    setattr(_thread_local, "from_mail_id", sender.pk)
                HorillaMailManager.send_mail(mail, context=context)
            except Exception as exc:
                logger.error(
                    "Assignment rule email send error (lead=%s): %s", lead.pk, exc
                )
            finally:
                if hasattr(_thread_local, "from_mail_id"):
                    delattr(_thread_local, "from_mail_id")

        threading.Thread(target=_send, daemon=True).start()

    except Exception as exc:
        logger.error("Assignment rule email setup error (lead=%s): %s", lead.pk, exc)


def _send_assignment_notification(condition, lead, assigned_user):
    """Send in-app notification to the assigned user using the condition's notification template."""
    try:
        tmpl = condition.notification_template
        if not tmpl:
            return

        context = {"instance": lead, "lead": lead}
        django_engine = engines["django"]
        msg_src = (
            ("{% load horilla_tags %}\n" + tmpl.message).strip() if tmpl.message else ""
        )
        message = (
            django_engine.from_string(msg_src).render(context)[:500]
            if msg_src
            else f"New lead assigned: {lead}"
        )

        lead_url = (
            str(lead.get_detail_url()) if hasattr(lead, "get_detail_url") else None
        )
        create_notification(
            user=assigned_user,
            message=message,
            sender=None,
            url=lead_url,
            instance=lead,
            read=False,
        )
    except Exception as exc:
        logger.error("Assignment rule notification error (lead=%s): %s", lead.pk, exc)


def apply_assignment_rules(lead):
    """
    Main assignment engine: evaluate active rules in order and apply the first matching condition.

    Steps:
    1. Iterate active LeadAssignmentRules ordered by creation date.
    2. For each rule, iterate its conditions (ordered by `order`).
    3. Evaluate criteria for each condition against the lead.
    4. On first match: pick the user with fewest leads (round-robin), update lead_owner,
       then send email / notification / both per the condition's notify_method.
    5. Stop after the first matching condition across all rules.
    """
    try:
        rules = LeadAssignmentRule.objects.filter(is_active=True).order_by("created_at")
        for rule in rules:
            conditions = LeadAssignmentCondition.objects.filter(rule=rule).order_by(
                "created_at"
            )

            for condition in conditions:
                if not _eval_condition_criteria(condition, lead):
                    continue

                # Condition matched — resolve target users
                users_qs = _resolve_target_users(condition)
                assigned_user = _pick_round_robin(users_qs)
                if not assigned_user:
                    logger.warning(
                        "Assignment rule '%s' condition #%s matched lead %s "
                        "but no eligible users found.",
                        rule.name,
                        condition.order,
                        lead.pk,
                    )
                    continue

                # Assign via direct UPDATE to avoid re-triggering post_save
                Lead.objects.filter(pk=lead.pk).update(lead_owner=assigned_user)
                lead.lead_owner = assigned_user  # keep in-memory object consistent
                logger.info(
                    "Lead %s assigned to %s via rule '%s'.",
                    lead.pk,
                    assigned_user.username,
                    rule.name,
                )

                # Deliver notifications / email
                method = condition.notify_method
                if method in ("email", "both"):
                    _send_assignment_email(condition, lead, assigned_user)
                if method in ("notification", "both"):
                    _send_assignment_notification(condition, lead, assigned_user)

                return  # first matching condition wins

    except Exception as exc:
        logger.error(
            "apply_assignment_rules error for lead %s: %s", lead.pk, exc, exc_info=True
        )


@receiver(post_save, sender=Lead)
def handle_lead_assignment(sender, instance, created, **kwargs):
    """
    Trigger assignment rules after a lead is created or updated.
    Deferred to on_commit to guarantee the row exists before querying.
    """

    def _run():
        try:
            lead = Lead.objects.get(pk=instance.pk)
            apply_assignment_rules(lead)
        except Lead.DoesNotExist:
            pass
        except Exception as exc:
            logger.error("handle_lead_assignment error (pk=%s): %s", instance.pk, exc)

    transaction.on_commit(_run)
