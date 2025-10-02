"""
Unit tests for db_i18n language helpers.
"""
from ecodev_core import Lang
from ecodev_core import SafeTestCase
from ecodev_core.db_i18n import get_lang
from ecodev_core.db_i18n import set_lang


class DbI18nContextTest(SafeTestCase):
    """Unit tests ensuring get_lang and set_lang behave as expected."""

    def setUp(self) -> None:
        """Reset language to default before each test."""
        super().setUp()

    def tearDown(self) -> None:
        """Restore the default language after each test."""
        super().tearDown()

    def test_get_lang_defaults_to_english(self) -> None:
        """get_lang returns English when nothing else is configured."""
        self.assertEqual(get_lang(), Lang.EN)

    def test_set_lang_updates_context(self) -> None:
        """Calling set_lang switches the active context language."""
        set_lang(Lang.FR)
        self.assertEqual(get_lang(), Lang.FR)
        set_lang(Lang.EN)
        self.assertEqual(get_lang(), Lang.EN)
