"""
Tests for Horilla _inherit_card card view extensions.
"""

from django.test import SimpleTestCase

from horilla.contrib.generics.views.card import HorillaCardView
from horilla.extension.card import clear_card_extension_cache, resolve_card_view_class
from horilla.extension.card.compose import compose_card_view_class
from horilla.extension.card.metaclass import CardExtension
from horilla.extension.card.registry import (
    CARD_COMPOSED_MAP,
    CARD_EXTENSION_REGISTRY,
    CardExtensionSpec,
    register_card_extension,
)


class _TargetCardView(HorillaCardView):
    """Minimal card target for compose tests."""

    model_name = "Lead"
    columns = ["title", "email"]


class _ExtCard(CardExtension):
    """Sample card extension registered against _TargetCardView."""

    _inherit_card = "horilla.extension.card.tests._TargetCardView"
    columns_insert = [("email", "industry_code")]


class CardExtensionMetaclassTests(SimpleTestCase):
    """Tests for CardExtension registration and validation."""

    def test_invalid_inherit_card_raises(self):
        """Reject _inherit_card paths without module.Class form."""
        with self.assertRaises(ValueError):

            class _BadCardExt(CardExtension):
                """Extension with invalid _inherit_card path."""

                _inherit_card = "invalid-no-dot"

    def test_extension_class_is_registered(self):
        """Registered extensions are flagged and cannot be instantiated."""
        self.assertTrue(getattr(_ExtCard, "_is_card_extension", False))
        with self.assertRaises(TypeError):
            _ExtCard()


class CardExtensionComposeTests(SimpleTestCase):
    """Tests for compose_card_view_class and composed card markers."""

    def setUp(self):
        """Isolate registry and register a single test extension spec."""
        clear_card_extension_cache()
        CARD_EXTENSION_REGISTRY.clear()
        CARD_COMPOSED_MAP.clear()
        register_card_extension(
            CardExtensionSpec(
                inherit_card="horilla.extension.card.tests._TargetCardView",
                class_name="_ExtCard",
                module="horilla.extension.card.tests",
                extension_app_label="tests",
                columns_insert=[("email", "industry_code")],
            )
        )

    def tearDown(self):
        """Restore registry and clear composed card cache."""
        clear_card_extension_cache()
        CARD_EXTENSION_REGISTRY.clear()
        CARD_COMPOSED_MAP.clear()

    def test_compose_mro_order(self):
        """Composed class MRO places extension mixin before target."""
        composed = compose_card_view_class(
            "horilla.extension.card.tests._TargetCardView",
            _TargetCardView,
        )
        mro_names = [c.__name__ for c in composed.mro()]
        self.assertEqual(mro_names[0], "_TargetCardViewExtended")
        self.assertIn("ExtCardMixin", mro_names)
        self.assertIn("_TargetCardView", mro_names)

    def test_columns_insert(self):
        """columns_insert places new columns after the anchor."""
        composed = compose_card_view_class(
            "horilla.extension.card.tests._TargetCardView",
            _TargetCardView,
        )
        self.assertEqual(
            composed.columns,
            ["title", "email", "industry_code"],
        )

    def test_composed_markers(self):
        """Composed card views expose __horilla_* marker attributes."""
        composed = compose_card_view_class(
            "horilla.extension.card.tests._TargetCardView",
            _TargetCardView,
        )
        self.assertTrue(composed.__horilla_card_composed__)
        self.assertEqual(
            composed.__horilla_card_path__,
            "horilla.extension.card.tests._TargetCardView",
        )

    def test_no_extensions_returns_target(self):
        """Without registered extensions, compose returns the target unchanged."""
        CARD_EXTENSION_REGISTRY.clear()
        composed = compose_card_view_class(
            "horilla.extension.card.tests._TargetCardView",
            _TargetCardView,
        )
        self.assertIs(composed, _TargetCardView)
