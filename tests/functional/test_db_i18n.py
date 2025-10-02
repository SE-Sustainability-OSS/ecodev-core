"""
Functional tests for the db_i18n helpers.
"""
from typing import Optional

from sqlmodel import Field
from sqlmodel import SQLModel

from ecodev_core import create_db_and_tables
from ecodev_core import delete_table
from ecodev_core import I18nMixin
from ecodev_core import Lang
from ecodev_core import localized_col
from ecodev_core import SafeTestCase
from ecodev_core import set_lang


class LocalizedRecord(I18nMixin, SQLModel, table=True):  # type: ignore[misc]
    """Simple SQLModel using I18nMixin for testing."""

    __tablename__ = 'localized_record'

    id: Optional[int] = Field(default=None, primary_key=True)
    name_en: Optional[str] = Field(default=None)
    name_fr: Optional[str] = Field(default=None)

    __localized_fields__ = {'name': [Lang.EN, Lang.FR]}
    __fallback_lang__ = Lang.EN


class PartialLocalizedModel(I18nMixin, SQLModel):  # type: ignore[misc]
    """Model missing the French translation for testing errors."""

    name_en: Optional[str] = None

    __localized_fields__ = {'name': [Lang.EN]}
    __fallback_lang__ = Lang.EN


class MissingFallbackModel(I18nMixin, SQLModel):  # type: ignore[misc]
    """Model with fallback language not configured in __localized_fields__."""

    name_fr: Optional[str] = None

    __localized_fields__ = {'name': [Lang.FR]}
    __fallback_lang__ = Lang.EN


class PlainModel(SQLModel, table=True):  # type: ignore[misc]
    """SQLModel without localization mixin."""

    __tablename__ = 'plain_model'

    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str] = Field(default=None)


class DbI18nTest(SafeTestCase):
    """Functional tests covering db_i18n behaviour."""

    def setUp(self):
        """Prepare database tables and reset language context."""
        super().setUp()
        set_lang(Lang.EN)
        create_db_and_tables(LocalizedRecord)
        delete_table(LocalizedRecord)

    def test_get_lang_chain_raises_for_unknown_field(self):
        """Requesting a non localized field raises an AttributeError."""
        with self.assertRaises(AttributeError):
            LocalizedRecord._get_lang_chain('title')

    def test_get_lang_chain_raises_for_missing_language(self):
        """Requesting an unavailable language raises an AttributeError."""
        with self.assertRaises(AttributeError):
            PartialLocalizedModel._get_lang_chain('name', Lang.FR)

    def test_get_lang_chain_raises_when_fallback_not_available(self):
        """Fallback language must be configured for the localized field."""
        with self.assertRaises(AttributeError):
            MissingFallbackModel._get_lang_chain('name')

    def test_get_lang_chain_order_with_explicit_language(self):
        """The requested language appears before the fallback language."""
        chain = LocalizedRecord._get_lang_chain('name', Lang.FR)
        self.assertEqual(chain, [Lang.FR, Lang.EN])

    def test_get_lang_chain_order_with_context_language(self):
        """Context language is considered before the fallback when no lang is set."""
        set_lang(Lang.FR)
        chain = LocalizedRecord._get_lang_chain('name')
        self.assertEqual(chain, [Lang.FR, Lang.EN])

    def test_get_localized_field_name_builds_expected_attribute(self):
        """_get_localized_field_name suffixes the field with the lang value."""
        self.assertEqual(
            LocalizedRecord._get_localized_field_name('name', Lang.EN),
            'name_en',
        )
        self.assertEqual(
            LocalizedRecord._get_localized_field_name('name', Lang.FR),
            'name_fr',
        )

    def test_get_localized_field_chain_returns_attribute_names(self):
        """get_localized_field_chain returns the localized attribute names."""
        set_lang(Lang.FR)
        chain = LocalizedRecord.get_localized_field_chain('name')
        self.assertEqual(chain, ['name_fr', 'name_en'])

    def test_get_localized_returns_requested_language(self):
        """_get_localized returns the value for the requested language when available."""
        record = LocalizedRecord(name_en='Hello', name_fr='Bonjour')
        self.assertEqual(record._get_localized('name', Lang.FR), 'Bonjour')

    def test_get_localized_uses_fallback_language(self):
        """When the requested language is missing, fallback value is returned."""
        set_lang(Lang.FR)
        record = LocalizedRecord(name_en='Hello', name_fr=None)
        self.assertEqual(record._get_localized('name'), 'Hello')

    def test_get_localized_returns_none_when_no_value(self):
        """_get_localized returns None when no translations are available."""
        set_lang(Lang.FR)
        record = LocalizedRecord(name_en=None, name_fr=None)
        self.assertIsNone(record._get_localized('name'))

    def test_dunder_getattr_returns_localized_value(self):
        """Accessing a localized field returns the localized value via __getattr__."""
        set_lang(Lang.FR)
        record = LocalizedRecord(name_en='Hello', name_fr='Bonjour')
        self.assertEqual(record.name, 'Bonjour')

    def test_dunder_getattr_raises_for_unknown_attribute(self):
        """__getattr__ raises AttributeError for non localized attributes."""
        record = LocalizedRecord(name_en='Hello', name_fr='Bonjour')
        with self.assertRaises(AttributeError):
            _ = record.title

    def test_localized_col_requires_i18n_mixin(self):
        """localized_col raises TypeError when the schema lacks the mixin."""
        with self.assertRaises(TypeError):
            localized_col('name', PlainModel)

    def test_localized_col_raises_for_unknown_field(self):
        """Requesting a non localized column raises an AttributeError."""
        with self.assertRaises(AttributeError):
            localized_col('title', LocalizedRecord)

    def test_localized_col_returns_coalesce_expression(self):
        """localized_col builds a label with requested and fallback columns."""
        column = localized_col('name', LocalizedRecord, lang=Lang.FR)
        self.assertEqual(column.name, 'name')
        clauses = list(column.element.clauses)
        self.assertEqual(clauses[0], LocalizedRecord.name_fr)
        self.assertEqual(clauses[1], LocalizedRecord.name_en)
