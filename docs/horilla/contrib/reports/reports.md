# Horilla Reports app — deep dive (`horilla.contrib.reports`)

## What this app does

- **ReportFolder** — hierarchical organization, favourites, owner-based access (`OWNER_FIELDS = ["folder_owner"]`).
- **Report** — saved definition: underlying model, columns, filters, chart configuration (stored as JSON / FKs—see `models.py` for schema evolution).
- Integrates with **dashboard** app (dashboard components can reference saved reports).
- **REST API** at `reports/`.

---

## App startup (`apps.py`)

`ReportsConfig`:

| Setting | Value |
|---------|--------|
| `url_prefix` | `reports/` |
| `url_namespace` | `reports` |
| `auto_import_modules` | `registration`, `signals`, `menu` |
| API | `reports/` → `horilla.contrib.reports.api.urls` |

---

## Menu (`menu.py`)

Registers main navigation / floating entries for **Reports list**, **builder**, and shortcuts. Default keyboard shortcuts may register on `User` post_save (see keys app) using `reports:reports_list_view`.

---

## Feature registration (`registration.py`)

- **`register_feature("report_choices", "report_models")`** — models that should appear as reportable modules register here.
- **`ReportFolder`** and **`Report`** — `register_model_for_feature` with `import_data`, `export_data`, `global_search`.

---

## Models — usage notes

### `ReportFolder`

- Self-FK **`parent_folder`** for nesting.
- **`favourited_by`** M2M for quick access.
- **`get_detail_view_url`** → `dashboard:dashboard_folder_detail_list` pattern for cross-app navigation (folders appear in dashboard navigator).

### `Report`

- **`report_owner`** FK — **`OWNER_FIELDS = ["report_owner"]`** for own vs all lists.
- **`module`** → `HorillaContentType`, limited by **`report_models`** feature registry.
- **`folder`** optional FK to `ReportFolder`.
- **Serialized query UI** — `selected_columns`, `row_groups`, `column_groups`, `aggregate_columns`, `filters` (see `*_list` properties on the model).
- **Chart** — `chart_type` (ECharts-oriented: column, line, funnel, sankey, …), `chart_field`, `chart_field_stacked`, `chart_value_field`.
- **Sharing** — `shared_with` M2M, `is_favourite` boolean.
- **`model_class`** property resolves the ORM class from `module`.

---

## Signals (`signals.py`)

May update denormalized counts when reports run on a schedule, or touch `RecentlyViewed`—read module for senders.

---

## Typical flows

1. User builds a **lead pipeline** chart → saves **Report** row in folder.
2. User pins report to **Dashboard** component → `DashboardComponent` references report PK (see dashboard models).
3. API consumer lists **`/reports/`** → serializer returns metadata without executing heavy query until `run` endpoint.

---

## Related documentation

- Dashboard models referencing `Report`: [../dashboard/dashboard.md](../dashboard/dashboard.md)
- Chart views in generics: [../generics/views/chart.md](../generics/views/chart.md)
