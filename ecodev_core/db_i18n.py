"""
Module implementing internationalization (i18n) for sqlmodel
"""
import contextvars
from enum import Enum
from typing import Optional

from sqlalchemy import Label
from sqlalchemy import label
from sqlmodel import func
from sqlmodel.main import SQLModelMetaclass


class Lang(str, Enum):
    """
    Enum of the languages available for localization.
    """
    EN = 'en'
    FR = 'fr'


DB_Lang = 'db_Lang'
CONTEXT_DB_Lang = contextvars.ContextVar(DB_Lang, default=Lang.EN)
"""Context variables for storing the active database language, defaults to Lang.EN"""


def set_lang(lang: Lang) -> None:
    """
    Sets the `CONTEXT_DB_Lang` context var.

    Args:
        lang (Lang): The language to assign to the `CONTEXT_DB_Lang` context var.
    """
    CONTEXT_DB_Lang.set(lang)


def get_lang() -> Lang:
    """
    Fetches the value of `CONTEXT_DB_Lang` context var.

    Returns:
        lang (Lang): The value of `CONTEXT_DB_Lang` context var
    """
    return Lang(CONTEXT_DB_Lang.get())


class I18nMixin:
    """
    I18n (localization) mixin for string attributes of pydantic BaseModel classes.

    Maps arbitrary string attributes of the class to their localized values. Localized fields 
    should be defined following the rules below :
        - The field name must be defined as a key of the private attribute `__localized_fields__`
        - Each field defined in `__localized_fields__` must be present as an attribute for \
            each of its localized versions in the following format <field>_<lang>.
            For example :
            ```
            __localized_fields__ = {
                'name':[Lang.EN, Lang.FR]
                }
            ```
            assumes that the attributes `name_en` and `name_fr` are attribute of the class.
            These attributes must have a type `str`.
        - All localized field must have a localized version using `__fallback_lang__`

    Args:
        __localized_fields__ (dict[str, list[Lang]]): Mapping between localized fields and a \
            list of their available localized versions. Defaults to {}.
        __fallback_lang__ (Lang): Fallback locale if the requested localized version of a \
            field is None. Defaults to Lang.EN.
    """
    __localized_fields__: dict[str, list[Lang]] = {}
    __fallback_lang__: Lang = Lang.EN

    @classmethod
    def _get_lang_chain(cls, field: str, lang: Optional[Lang] = None) -> list[Lang]:
        """
        Returns the chain of localized versions of the requested field with the priority given
        to the `lang` argument, followed by the lang returned by
        [get_lang][ecodev_core.db_i18n.get_lang] and finally the lang defined in
        `cls.__fallback_lang__`.

        Args:
            field (str): Name of the attribute/field to localize
            lang (Optional[Lang]): The requested locale language. If none, then uses that
            returned by [get_lang][ecodev_core.db_i18n.get_lang]. Defaults to None.

        Returns:
            list[Lang]: List of Lang enums to use for generating the name of the localized \
                fields.
        """
        if field not in cls.__localized_fields__:
            raise AttributeError(f'Field {field!r} is not internationalized.')
        
        available_langs = cls.__localized_fields__[field]
        
        if cls.__fallback_lang__ not in available_langs:
            raise AttributeError(
                f'Fallback language {cls.__fallback_lang__!r} not available for field {field!r}. '
                f'Available: {available_langs}'
            )
        
        lang = lang or get_lang()
        if lang not in cls.__localized_fields__[field]:
            raise AttributeError(f'Field {field!r} is not localized to {lang!r}')

        return [lang] if cls.__fallback_lang__ == lang else [lang, cls.__fallback_lang__]

    @classmethod
    def _get_localized_field_name(cls, field: str, lang: Lang) -> str:
        """
        Returns the name of the localized version of `field` for the requested `lang` in the
        following format <field>_<lang>.

        Args:
            field (str): Name of the attribute/field to localize
            lang (Optional[Lang]): The requested locale language.
        Returns:
            str: the name of the localized version of `field` for the requested `lang`
        """
        return f'{field}_{lang.value}'

    @classmethod
    def get_localized_field_chain(cls, field: str, lang: Optional[Lang] = None) -> list[str]:
        """
        Returns a chain of the localized versions of the requested field with the priority given
        to the `lang` argument, followed by the lang returned by
        [get_lang][ecodev_core.db_i18n.get_lang] and finally
        the lang defined in `cls.__fallback_lang__`

        Args:
            field (str): Name of the attribute/field to localize
            lang (Optional[Lang]): The requested locale language. If none, then uses that
            returned by [get_lang][ecodev_core.db_i18n.get_lang]. Defaults to None.

        Returns:
            list[str]: chain of the localized versions of the requested field.

        """
        return [cls._get_localized_field_name(field, lang) 
                for lang in cls._get_lang_chain(field, lang)]

    def _get_localized(self, field: str, lang: Optional[Lang] = None) -> Optional[str]:
        """
        Returns the localized version of a field.

        The localized version is returned following the rules defined below :
            - If the requested localized version is not available then the an attempt \
                will be made to localize the field using `__fallback_lang__`
            - The specified language can be passed to `_get_localized`. If it is not passed, \
                the value returned by [get_lang][ecodev_core.db_i18n.get_lang]
                is  used instead (Defaults to Lang.EN)
            - If None is returned using the format <field>_<lang> for the language defined in \
                `__localized_fields__` & `__fallback_lang__` is found then returns None

        Args:
            field (str): Name of the attribute/field to localize
            lang (Optional[Lang]): Requested locale. If None, then fetched from \
                [get_lang][ecodev_core.db_i18n.get_lang]. Defaults to None.

        Return:
            localized_field (Optional[str]): localized version of the field
        """
        lang_chain = self._get_lang_chain(field=field, lang=lang)

        for lang in lang_chain:
            attr = self._get_localized_field_name(field=field, lang=lang)
            value = getattr(self, attr, None)
            if value:
                return value

        return None

    def __getattr__(self, item: str) -> Optional[str]:
        """
        Overrides __getattr__ to get the localized value of a item if it figures in
        `__localized_fields__`.
        """
        if item in self.__localized_fields__:
            return self._get_localized(item)
        raise AttributeError(f'{self.__class__.__name__!r} object has no attribute {item!r}')


def localized_col(
    field: str,
    db_schema: SQLModelMetaclass,
    lang: Optional[Lang] = None,
) -> Label:
    """
    Returns the localized version of `field` for the requested `lang` of a
    given SqlModel class. If `lang` is not specified, then fetches the active
    locale from [get_lang][ecodev_core.db_i18n.get_lang].

    Args:
        field (str): Name of the field to localize
        db_schema (SQLModelMetaclass): SQLModelMetaclass instance from which the localized \
            fields will be fetched
        lang (Optional[Lang]): Requested locale language. If None, then fetches language \
            from [get_lang][ecodev_core.db_i18n.get_lang] Defaults to None.

    Returns:
        localized_field (Label): Localized version of the requested `field` wrapped in label \
            with the name of `field`.
    """
    if not issubclass(db_schema, I18nMixin):
        raise TypeError(f"{db_schema.__name__} does not inherit from I18nMixin")
    
    localized_fields_chain = db_schema.get_localized_field_chain(field, lang)
    coalesce_fields = [getattr(db_schema, field_name) for field_name in localized_fields_chain]

    return label(field, func.coalesce(*coalesce_fields))
