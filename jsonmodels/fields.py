import datetime
import re
from typing import List, Optional, Dict, Union, Pattern, Type, Any, Set
from weakref import WeakKeyDictionary

import six
from dateutil.parser import parse
from pydantic import Field, BaseModel
from pydantic.fields import FieldInfo

from .collections import ModelCollection
from .errors import RequiredFieldError, BadTypeError, AmbiguousTypeError

# unique marker for "no default value specified". None is not good enough since
# it is a completely valid default value.
NotSet = object()

# BSON compatible types, which can be returned by toBsonEncodable.
BsonEncodable = Union[
    float, str, object, Dict, List, bytes, bool, datetime.datetime, None,
    Pattern, int, bytes
]


def BaseField(
    required=False,
    nullable=False,
    help_text=None,
    validators=None,
    name=None,
    default=NotSet,
):
    field_info = Field(
        description=help_text,
        alias=name,
        title=name,
        required=required,
        default=None if default is NotSet else default,
    )

    class BaseFieldInfo(FieldInfo):
        def parse_value(self, value):
            class Test(BaseModel):
                field = self
            return Test(field=value).field

    return BaseFieldInfo(default=field_info)


def StringField(*args, **kwargs) -> str:
    return BaseField(*args, **kwargs)


def IntField(*args, **kwargs) -> int:
    def parse_value(value):
        """Cast value to `int`, e.g. from string or long"""
        parsed = value
        if parsed is None:
            return parsed
        try:
            return int(parsed)
        except ValueError:
            raise BadTypeError(value, types=(int,), is_list=False)

    return BaseField(*args, **kwargs)


def FloatField(*args, **kwargs) -> float:
    return BaseField(*args, **kwargs)


def BoolField(*args, **kwargs):
    return BaseField(*args, **kwargs)


# class ListField(BaseField):
#
#     """List field."""
#
#     types = (list, tuple)
#
#     def __init__(self, items_types=None, item_validators=(), omit_empty=False,
#                  *args, **kwargs):
#         """Init.
#
#         `ListField` is **always not required**. If you want to control number
#         of items use validators. If you want to validate each individual item,
#         use `item_validators`. You may pass omit_empty so empty lists are not
#         included in the to_struct method.
#
#         """
#         self._assign_types(items_types)
#         self.item_validators = [item_validators] \
#             if item_validators and not isinstance(item_validators, list) \
#             else item_validators or []
#         super(ListField, self).__init__(*args, **kwargs)
#         self.required = False
#         self._omit_empty = omit_empty
#
#     def get_default_value(self):
#         default = super(ListField, self).get_default_value()
#         if default is None:
#             return ModelCollection(self)
#         return default
#
#     def _assign_types(self, items_types):
#         if items_types:
#             try:
#                 self.items_types = tuple(items_types)
#             except TypeError:
#                 self.items_types = items_types,
#         else:
#             self.items_types = tuple()
#
#         types = []
#         for type_ in self.items_types:
#             if isinstance(type_, six.string_types):
#                 types.append(_LazyType(type_))
#             else:
#                 types.append(type_)
#         self.items_types = tuple(types)
#
#     def validate(self, value):
#         super(ListField, self).validate(value)
#
#         for item in value:
#             self.validate_single_value(item)
#
#     def validate_single_value(self, value):
#         for validator in self.item_validators:
#             try:
#                 validator.validate(value)
#             except AttributeError:
#                 validator(value)
#
#         if len(self.items_types) == 0:
#             return
#
#         if not isinstance(value, self.items_types):
#             raise BadTypeError(value, self.items_types, is_list=True)
#
#     def parse_value(self, values):
#         """Cast value to proper collection."""
#         result = self.get_default_value()
#
#         if not values:
#             return result
#
#         if not isinstance(values, list):
#             return values
#
#         return [self._cast_value(value) for value in values]
#
#     def _cast_value(self, value):
#         if isinstance(value, self.items_types):
#             return value
#         elif isinstance(value, dict):
#             model_type = self._get_embed_type(value, self.items_types)
#             return model_type(**value)
#         else:
#             raise BadTypeError(value, self.items_types, is_list=True)
#
#     def _finish_initialization(self, owner):
#         """
#         Makes sure the list field is initialized, converting any
#         `_LazyType` references for the items.
#         """
#         super(ListField, self)._finish_initialization(owner)
#
#         types = []
#         for item_type in self.items_types:
#             if isinstance(item_type, _LazyType):
#                 types.append(item_type.evaluate(owner))
#             else:
#                 types.append(item_type)
#         self.items_types = tuple(types)
#
#     def _elem_to_struct(self, value):
#         try:
#             return value.to_struct()
#         except AttributeError:
#             return value
#
#     def to_struct(self, values):
#         return [self._elem_to_struct(v) for v in values] \
#             if values or not self._omit_empty else None
#
#
# class DerivedListField(ListField):
#     """
#     A list field that has another field for its items.
#     """
#
#     def __init__(self, field: BaseField, *args, **kwargs):
#         """
#         :param field: The field that will be in each of the items of the list.
#         :param help_text: The help text of the list field.
#         :param validators: The validators for the list field.
#         """
#         self._field = field
#         super(DerivedListField, self).__init__(
#             items_types=field.types,
#             item_validators=field.validators,
#             *args, **kwargs,
#         )
#
#     def _finish_initialization(self, owner):
#         """
#         Makes sure the derived list field is initialized, converting any
#         `_LazyType` references. Initializes both the base list field and
#         the child field.
#         """
#         super()._finish_initialization(owner)
#         self._field._finish_initialization(owner)
#
#     def to_struct(self, values: List[any]) -> List[any]:
#         """
#         Converts the list to its output format.
#         :param values: The values in the list.
#         :return: The converted values.
#         """
#         return [self._field.to_struct(value) for value in values] \
#             if values or not self._omit_empty else None
#
#     def parse_value(self, values: List[any]) -> List[any]:
#         """
#         Converts the list to its internal format.
#         :param values: The values in the list.
#         :return: The converted values.
#         """
#         try:
#             return [self._field.parse_value(value) for value in values]
#         except TypeError:
#             raise BadTypeError(values, self._field.types, is_list=True)
#
#     def validate_single_value(self, value: any) -> None:
#         """
#         Validates a single value in the list.
#         :param value: One of the values in the list.
#         """
#         self._field.validate(value)
#
#
# class EmbeddedField(BaseField):
#
#     """Field for embedded models."""
#
#     def __init__(self, model_types, *args, **kwargs):
#         self._assign_model_types(model_types)
#         super(EmbeddedField, self).__init__(*args, **kwargs)
#
#     def _assign_model_types(self, model_types):
#         if not isinstance(model_types, (list, tuple)):
#             model_types = (model_types,)
#
#         types = []
#         for type_ in model_types:
#             if isinstance(type_, six.string_types):
#                 types.append(_LazyType(type_))
#             else:
#                 types.append(type_)
#         self.types = tuple(types)
#
#     def _finish_initialization(self, owner):
#         super(EmbeddedField, self)._finish_initialization(owner)
#         types = []
#         for model_type in self.types:
#             if isinstance(model_type, _LazyType):
#                 types.append(model_type.evaluate(owner))
#             else:
#                 types.append(model_type)
#
#         self.types = tuple(types)
#
#     def validate(self, value):
#         super(EmbeddedField, self).validate(value)
#         try:
#             value.validate()
#         except AttributeError:
#             pass
#
#     def parse_value(self, value):
#         """Parse value to proper model type."""
#         if not isinstance(value, dict):
#             return value
#
#         embed_type = self._get_embed_type(value, self.types)
#         return embed_type(**value)
#
#     def to_struct(self, value):
#         return value.to_struct()
#
#
# class MapField(BaseField):
#     """
#     Model field that keeps a mapping between two other fields.
#     It is basically a dictionary with key and values being separate fields.
#
#     `MapField` is **always not required**. If you want to control number
#     of items use validators. You may pass omit_empty so empty lists are not
#     included in the to_struct method.
#
#     """
#     types = (dict,)
#
#     def __init__(self, key_field: BaseField, value_field: BaseField,
#                  **kwargs):
#         """
#         :param key_field: The field that is responsible for converting and
#             validating the keys in this mapping.
#         :param value_field: The field that is responsible for converting and
#             validating the values in this mapping.
#         :param kwargs: Other keyword arguments to the base class.
#         """
#         super(MapField, self).__init__(**kwargs)
#         self._key_field = key_field
#         self._value_field = value_field
#
#     def _finish_initialization(self, owner):
#         """
#         Completes the initialization of the fields, allowing for lazy refs.
#         """
#         super(MapField, self)._finish_initialization(owner)
#         self._key_field._finish_initialization(owner)
#         self._value_field._finish_initialization(owner)
#
#     def get_default_value(self) -> any:
#         """ Gets the default value for this field """
#         default = super(MapField, self).get_default_value()
#         if default is None and self.required:
#             return dict()
#         return default
#
#     def parse_value(self, values: Optional[dict]) -> Optional[dict]:
#         """ Parses the given values into a new dict. """
#         values = super().parse_value(values)
#         if values is None:
#             return
#         items = [
#             (self._key_field.parse_value(key),
#              self._value_field.parse_value(value))
#             for key, value in values.items()
#         ]
#         return type(values)(items)  # Preserves OrderedDict
#
#     def to_struct(self, values: Optional[dict]) -> Optional[dict]:
#         """ Casts the field values into a dict. """
#         items = [
#             (self._key_field.to_struct(key),
#              self._value_field.to_struct(value))
#             for key, value in values.items()
#         ]
#         return type(values)(items)  # Preserves OrderedDict
#
#     def validate(self, values: Optional[dict]) -> Optional[dict]:
#         """
#         Validates all keys and values in the map field.
#         :param values: The values in the mapping.
#         """
#         super(MapField, self).validate(values)
#         if values is None:
#             return
#         for key, value in values.items():
#             self._key_field.validate(key)
#             self._value_field.validate(value)
#
#
# class _LazyType(object):
#     """
#     Class used to temporarily save a class name to be used as reference in
#     the JSON models. It is automatically created whenever the class
#     reference is a string. This allows types to be referenced in
#     Embedded/List fields that have not been declared yet. That is necessary
#     for circular and recursive references in the models.
#     """
#
#     def __init__(self, path: str):
#         self.path = path
#
#     def evaluate(self, base_cls: Type[Any]):
#         module, type_name = _evaluate_path(self.path, base_cls)
#         return _import(module, type_name)
#
#
# def _evaluate_path(relative_path: str, base_cls: Type[Any]):
#     base_module = base_cls.__module__
#
#     modules = _get_modules(relative_path, base_module)
#
#     type_name = modules.pop()
#     module = '.'.join(modules)
#     if not module:
#         module = base_module
#     return module, type_name
#
#
# def _get_modules(relative_path, base_module):
#     canonical_path = relative_path.lstrip('.')
#     canonical_modules = canonical_path.split('.')
#
#     if not relative_path.startswith('.'):
#         return canonical_modules
#
#     parents_amount = len(relative_path) - len(canonical_path)
#     parent_modules = base_module.split('.')
#     parents_amount = max(0, parents_amount - 1)
#     if parents_amount > len(parent_modules):
#         raise ValueError("Can't evaluate path '{}'".format(relative_path))
#     return parent_modules[:parents_amount * -1] + canonical_modules
#
#
# def _import(module_name, type_name):
#     module = __import__(module_name, fromlist=[type_name])
#     try:
#         return getattr(module, type_name)
#     except AttributeError:
#         raise ValueError(
#             "Can't find type '{}.{}'.".format(module_name, type_name))
#
#
# class TimeField(StringField):
#
#     """Time field."""
#
#     types = (datetime.time,)
#
#     def __init__(self, str_format=None, *args, **kwargs):
#         """Init.
#
#         :param str str_format: Format to cast time to (if `None` - casting to
#             ISO 8601 format).
#
#         """
#         self.str_format = str_format
#         super(TimeField, self).__init__(*args, **kwargs)
#
#     def to_struct(self, value):
#         """Cast `time` object to string."""
#         if self.str_format:
#             return value.strftime(self.str_format)
#         return value.isoformat()
#
#     def parse_value(self, value):
#         """Parse string into instance of `time`."""
#         if value is None:
#             return value
#         if isinstance(value, datetime.time):
#             return value
#         return parse(value).timetz()
#
#
# class DateField(StringField):
#
#     """Date field."""
#
#     types = (datetime.date,)
#     default_format = '%Y-%m-%d'
#
#     def __init__(self, str_format=None, *args, **kwargs):
#         """Init.
#
#         :param str str_format: Format to cast date to (if `None` - casting to
#             %Y-%m-%d format).
#
#         """
#         self.str_format = str_format
#         super(DateField, self).__init__(*args, **kwargs)
#
#     def to_struct(self, value):
#         """Cast `date` object to string."""
#         if self.str_format:
#             return value.strftime(self.str_format)
#         return value.strftime(self.default_format)
#
#     def parse_value(self, value):
#         """Parse string into instance of `date`."""
#         if value is None:
#             return value
#         if isinstance(value, datetime.date):
#             return value
#         return parse(value).date()
#
#
# class DateTimeField(StringField):
#
#     """Datetime field."""
#
#     types = (datetime.datetime,)
#
#     def __init__(self, str_format=None, *args, **kwargs):
#         """Init.
#
#         :param str str_format: Format to cast datetime to (if `None` - casting
#             to ISO 8601 format).
#
#         """
#         self.str_format = str_format
#         super(DateTimeField, self).__init__(*args, **kwargs)
#
#     def to_struct(self, value):
#         """Cast `datetime` object to string."""
#         if self.str_format:
#             return value.strftime(self.str_format)
#         return value.isoformat()
#
#     def toBsonEncodable(self, value: datetime) -> datetime:
#         """
#         Keep datetime object a datetime object, since pymongo supports that.
#         """
#         if not isinstance(value, self.types):
#             raise BadTypeError(value, self.types, is_list=False)
#         return value
#
#     def parse_value(self, value):
#         """Parse string into instance of `datetime`."""
#         if isinstance(value, datetime.datetime):
#             return value
#         if value:
#             return parse(value)
#         else:
#             return None
#
#
# class GenericField(BaseField):
#     """
#     Field that supports any kind of value, converting models to their correct
#     struct, keeping ordered dictionaries in their original order.
#     """
#     types = (any,)
#
#     def _validate_against_types(self, value) -> None:
#         pass
#
#     def to_struct(self, values: any) -> any:
#         """ Casts value to Python structure. """
#         from .models import Base
#         if isinstance(values, Base):
#             return values.to_struct()
#
#         if isinstance(values, (list, tuple)):
#             return [self.to_struct(value) for value in values]
#
#         if isinstance(values, dict):
#             items = [(self.to_struct(key), self.to_struct(value))
#                      for key, value in values.items()]
#             return type(values)(items)  # preserves OrderedDict
#
#         return values
