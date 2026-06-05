"""
Tests for Horilla _inherit_list list view extensions.
"""

from django.test import SimpleTestCase
from django.views.generic import ListView

from horilla.extension.list import clear_list_extension_cache, resolve_list_view_class
from horilla.extension.list.compose import compose_list_view_class
from horilla.extension.list.metaclass import ListExtension
from horilla.extension.list.registry import (
    LIST_COMPOSED_MAP,
    LIST_EXTENSION_REGISTRY,
    ListExtensionSpec,
    register_list_extension,
)


class _TargetListView(ListView):
    """Minimal ListView target for compose tests."""

    columns = ["alpha", "beta"]
    bulk_update_fields = ["alpha"]


class _ExtList(ListExtension):
    """Sample list extension registered against _TargetListView."""

    _inherit_list = "horilla.extension.list.tests._TargetListView"
    columns_insert = [("beta", "gamma")]
    bulk_update_fields_append = ["gamma"]


class ListExtensionMetaclassTests(SimpleTestCase):
    """Tests for ListExtension registration and validation."""

    def test_invalid_inherit_list_raises(self):
        """Reject _inherit_list paths without module.Class form."""
        with self.assertRaises(ValueError):

            class _BadListExt(ListExtension):
                """Extension with invalid _inherit_list path."""

                _inherit_list = "invalid-no-dot"

    def test_extension_class_is_registered(self):
        """Registered extensions are flagged and cannot be instantiated."""
        self.assertTrue(getattr(_ExtList, "_is_list_extension", False))
        with self.assertRaises(TypeError):
            _ExtList()


class ListExtensionComposeTests(SimpleTestCase):
    """Tests for compose_list_view_class and composed view markers."""

    def setUp(self):
        """Isolate registry and register a single test extension spec."""
        self._saved_registry = {k: list(v) for k, v in LIST_EXTENSION_REGISTRY.items()}
        clear_list_extension_cache()
        LIST_EXTENSION_REGISTRY.clear()
        LIST_COMPOSED_MAP.clear()
        register_list_extension(
            ListExtensionSpec(
                inherit_list="horilla.extension.list.tests._TargetListView",
                class_name="_ExtList",
                module="horilla.extension.list.tests",
                extension_app_label="tests",
                columns_insert=[("beta", "gamma")],
                bulk_update_fields_append=["gamma"],
                class_attrs={},
            )
        )

    def tearDown(self):
        """Restore registry and clear composed view cache."""
        clear_list_extension_cache()
        LIST_EXTENSION_REGISTRY.clear()
        LIST_EXTENSION_REGISTRY.update(self._saved_registry)
        LIST_COMPOSED_MAP.clear()

    def test_compose_mro_order(self):
        """Composed class MRO places extension mixin before target."""
        composed = compose_list_view_class(
            "horilla.extension.list.tests._TargetListView",
            _TargetListView,
        )
        mro_names = [c.__name__ for c in composed.mro()]
        self.assertEqual(mro_names[0], "_TargetListViewExtended")
        self.assertIn("ExtListMixin", mro_names)
        self.assertIn("_TargetListView", mro_names)
        self.assertLess(
            mro_names.index("ExtListMixin"),
            mro_names.index("_TargetListView"),
        )

    def test_columns_insert(self):
        """columns_insert appends fields after the anchor column."""
        composed = compose_list_view_class(
            "horilla.extension.list.tests._TargetListView",
            _TargetListView,
        )
        self.assertEqual(composed.columns, ["alpha", "beta", "gamma"])

    def test_bulk_update_fields_append(self):
        """bulk_update_fields_append unions with target bulk_update_fields."""
        composed = compose_list_view_class(
            "horilla.extension.list.tests._TargetListView",
            _TargetListView,
        )
        self.assertEqual(composed.bulk_update_fields, ["alpha", "gamma"])

    def test_composed_markers(self):
        """Composed views expose __horilla_list_* marker attributes."""
        composed = compose_list_view_class(
            "horilla.extension.list.tests._TargetListView",
            _TargetListView,
        )
        self.assertTrue(composed.__horilla_list_composed__)
        self.assertEqual(
            composed.__horilla_list_path__,
            "horilla.extension.list.tests._TargetListView",
        )
        self.assertIs(composed.__wrapped_list_view__, _TargetListView)

    def test_resolve_returns_composed(self):
        """resolve_list_view_class returns the composed subclass."""
        from horilla.extension.list.bootstrap import apply_list_extensions

        apply_list_extensions(force=True)
        LIST_COMPOSED_MAP["horilla.extension.list.tests._TargetListView"] = (
            compose_list_view_class(
                "horilla.extension.list.tests._TargetListView",
                _TargetListView,
            )
        )
        resolved = resolve_list_view_class(_TargetListView)
        self.assertIsNot(resolved, _TargetListView)
        self.assertTrue(resolved.__horilla_list_composed__)

    def test_no_extensions_returns_target(self):
        """Empty registry returns the original target view class."""
        LIST_EXTENSION_REGISTRY.clear()
        composed = compose_list_view_class(
            "horilla.extension.list.tests._TargetListView",
            _TargetListView,
        )
        self.assertIs(composed, _TargetListView)


class ListExtensionLeadIntegrationTests(SimpleTestCase):
    """Integration tests with my_lead_extensions Lead list extension."""

    def setUp(self):
        """Import my_lead_extensions.lists to populate the registry."""
        clear_list_extension_cache()
        import importlib

        importlib.import_module("my_lead_extensions.lists")

        self.addCleanup(clear_list_extension_cache)

    def test_lead_list_extension_registers_when_imported(self):
        """LeadListExtension registers against LeadListView path."""
        specs = LIST_EXTENSION_REGISTRY.get(
            "horilla_crm.leads.views.core.LeadListView",
            [],
        )
        self.assertTrue(any(s.class_name == "LeadListExtension" for s in specs))

    def test_lead_list_compose_includes_industry_code(self):
        """Composed LeadListView includes industry_code column and bulk field."""
        from horilla.extension.list.bootstrap import apply_list_extensions
        from horilla_crm.leads.views.core import LeadListView

        self.assertTrue(
            any(
                s.class_name == "LeadListExtension"
                for s in LIST_EXTENSION_REGISTRY.get(
                    "horilla_crm.leads.views.core.LeadListView",
                    [],
                )
            )
        )
        apply_list_extensions(force=True)
        resolved = resolve_list_view_class(LeadListView)
        column_keys = []
        for col in resolved.columns:
            if isinstance(col, str):
                column_keys.append(col)
            elif isinstance(col, (list, tuple)) and len(col) >= 2:
                column_keys.append(col[1])
        self.assertIn("industry_code", column_keys)
        self.assertIn("industry_code", resolved.bulk_update_fields)
