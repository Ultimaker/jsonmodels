import warnings
from weakref import WeakKeyDictionary

import datetime
import re
import six
from dateutil.parser import parse
from typing import List, Optional, Dict, Set, Union, Pattern

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


class BaseField(object):

    """Base class for all fields."""

    types = None

    def __init__(
            self,
            required=False,
            nullable=False,
            help_text=None,
            validators=None,
            default=NotSet,
            name=None):
        self.memory = WeakKeyDictionary()
        self.required = required
        self.help_text = help_text
        self.nullable = nullable
        self._assign_validators(validators)
        self.name = name
        self._validate_name()
        if default is not NotSet:
            self.validate(default)
        self._default = default

    @property
    def has_default(self):
        return self._default is not NotSet

    def _assign_validators(self, validators):
        if validators and not isinstance(validators, list):
            validators = [validators]
        self.validators = validators or []

    def __set__(self, instance, value):
        self._finish_initialization(type(instance))
        value = self.parse_value(value)
        self.validate(value)
        self.memory[instance._cache_key] = value

    def __get__(self, instance, owner=None):
        if instance is None:
            self._finish_initialization(owner)
            return self

        self._finish_initialization(type(instance))

        self._check_value(instance)
        return self.memory[instance._cache_key]

    def _finish_initialization(self, owner):
        pass

    def _check_value(self, obj):
        if obj._cache_key not in self.memory:
            self.__set__(obj, self.get_default_value())

    def validate_for_object(self, obj):
        value = self.__get__(obj)
        self.validate(value)

    def validate(self, value):
        self._check_types()
        self._validate_against_types(value)
        self._check_against_required(value)
        self._validate_with_custom_validators(value)

    def _check_against_required(self, value):
        if value is None and self.required:
            raise RequiredFieldError()

    def _validate_against_types(self, value):
        if value is not None and not isinstance(value, self.types):
            raise BadTypeError(value, self.types, is_list=False)

    def _check_types(self):
        if self.types is None:
            tpl = 'Field "{type}" is not usable, try different field type.'
            raise ValueError(tpl.format(type=type(self).__name__))

    @staticmethod
    def _get_embed_type(value, models):
        """
        Tries to guess which of the given models is applicable to the dict.
        :param value: The dict to check.
        :param models: A list of acceptable models.
        :return: A single model from the list that contains all the fields
        that are also in the dict.
        :raise AmbiguousTypeError: If more than one model is matched.
        """
        if len(models) > 1:
            # dict of the available fields per model, so we can automatically
            # recognize dicts
            model_fields = {
                model: {
                   name or attr for attr, name, field
                   in model.iterate_with_name()
                } for model in models
                if hasattr(model, "iterate_with_name")
            }  # type: Dict[type, Set[str]]
            matching_models = [model for model, fields in model_fields.items()
                               if fields.issuperset(value)]

            if len(matching_models) != 1:
                raise AmbiguousTypeError(models)

            # this is the only model that has all given fields
            return matching_models[0]
        return models[0]

    def toBsonEncodable(self, value: types) -> BsonEncodable:
        """Optionally return a bson encodable python object.

        Returned object should be BSON compatible. By default uses the
        `to_struct` method, which creates JSON compatible types. JSON is
        compatible with bson, but only has support for limited types. When
        required, this method should cast the value to supported bson type.
        See: https://api.mongodb.com/python/current/api/bson/index.html

        For example: when a value is a datetime object return it as a datetime
        object. When a value is of CustomDateObject, cast it to a datetime
        object before returning it.

        :param value: Value
        :return: a value which should be bson encodable
        """
        return self.to_struct(value=value)

    def to_struct(self, value):
        """Cast value to Python dict."""
        return value

    def parse_value(self, value):
        """Parse value from primitive to desired format.

        Each field can parse value to form it wants it to be (like string or
        int).

        """
        return value

    def _validate_with_custom_validators(self, value):
        if value is None and self.nullable:
            return

        for validator in self.validators:
            try:
                validator.validate(value)
            except AttributeError:
                validator(value)

    def get_default_value(self):
        """Get default value for field.

        Each field can specify its default.

        """
        return self._default if self.has_default else None

    def _validate_name(self):
        if self.name is None:
            return
        if not re.match(r'^[A-Za-z_](([\w\-]*)?\w+)?$', self.name):
            raise ValueError('Wrong name', self.name)

    def structure_name(self, default):
        return self.name if self.name is not None else default

    def structue_name(self, default):
        warnings.warn("`structue_name` is deprecated, please use "
                      "`structure_name`")
        return self.structure_name(default)


class StringField(BaseField):

    """String field."""

    types = six.string_types


class IntField(BaseField):

    """Integer field."""

    types = (int,)

    def parse_value(self, value):
        """Cast value to `int`, e.g. from string or long"""
        parsed = super(IntField, self).parse_value(value)
        if parsed is None:
            return parsed
        try:
            return int(parsed)
        except ValueError:
            raise BadTypeError(value, types=(int,), is_list=False)


class FloatField(BaseField):

    """Float field."""

    types = (float, int)


class BoolField(BaseField):

    """Bool field."""

    types = (bool,)

    def parse_value(self, value):
        """Cast value to `bool`."""
        parsed = super(BoolField, self).parse_value(value)
        return bool(parsed) if parsed is not None else None


class ListField(BaseField):

    """List field."""

    types = (list, tuple)

    def __init__(self, items_types=None, item_validators=(), omit_empty=False,
                 *args, **kwargs):
        """Init.

        `ListField` is **always not required**. If you want to control number
        of items use validators. If you want to validate each individual item,
        use `item_validators`. You may pass omit_empty so empty lists are not
        included in the to_struct method.

        """
        self._assign_types(items_types)
        self.item_validators = [item_validators] \
            if item_validators and not isinstance(item_validators, list) \
            else item_validators or []
        super(ListField, self).__init__(*args, **kwargs)
        self.required = False
        self._omit_empty = omit_empty

    def get_default_value(self):
        default = super(ListField, self).get_default_value()
        if default is None:
            return ModelCollection(self)
        return default

    def _assign_types(self, items_types):
        if items_types:
            try:
                self.items_types = tuple(items_types)
            except TypeError:
                self.items_types = items_types,
        else:
            self.items_types = tuple()

        types = []
        for type_ in self.items_types:
            if isinstance(type_, six.string_types):
                types.append(_LazyType(type_))
            else:
                types.append(type_)
        self.items_types = tuple(types)

    def validate(self, value):
        super(ListField, self).validate(value)

        for item in value:
            self.validate_single_value(item)

    def validate_single_value(self, value):
        for validator in self.item_validators:
            try:
                validator.validate(value)
            except AttributeError:
                validator(value)

        if len(self.items_types) == 0:
            return

        if not isinstance(value, self.items_types):
            raise BadTypeError(value, self.items_types, is_list=True)

    def parse_value(self, values):
        """Cast value to proper collection."""
        result = self.get_default_value()

        if not values:
            return result

        if not isinstance(values, list):
            return values

        return [self._cast_value(value) for value in values]

    def _cast_value(self, value):
        if isinstance(value, self.items_types):
            return value
        elif isinstance(value, dict):
            model_type = self._get_embed_type(value, self.items_types)
            return model_type(**value)
        else:
            raise BadTypeError(value, self.items_types, is_list=True)

    def _finish_initialization(self, owner):
        super(ListField, self)._finish_initialization(owner)

        types = []
        for item_type in self.items_types:
            if isinstance(item_type, _LazyType):
                types.append(item_type.evaluate(owner))
            else:
                types.append(item_type)
        self.items_types = tuple(types)

    def _elem_to_struct(self, value):
        try:
            return value.to_struct()
        except AttributeError:
            return value

    def to_struct(self, values):
        return [self._elem_to_struct(v) for v in values] \
            if values or not self._omit_empty else None


class DerivedListField(ListField):
    """
    A list field that has another field for its items.
    """

    def __init__(self, field: BaseField, *args, **kwargs):
        """
        :param field: The field that will be in each of the items of the list.
        :param help_text: The help text of the list field.
        :param validators: The validators for the list field.
        """
        self._field = field
        super(DerivedListField, self).__init__(
            items_types=field.types,
            item_validators=field.validators,
            *args, **kwargs,
        )

    def to_struct(self, values: List[any]) -> List[any]:
        """
        Converts the list to its output format.
        :param values: The values in the list.
        :return: The converted values.
        """
        return [self._field.to_struct(value) for value in values] \
            if values or not self._omit_empty else None

    def parse_value(self, values: List[any]) -> List[any]:
        """
        Converts the list to its internal format.
        :param values: The values in the list.
        :return: The converted values.
        """
        try:
            return [self._field.parse_value(value) for value in values]
        except TypeError:
            raise BadTypeError(values, self._field.types, is_list=True)

    def validate_single_value(self, value: any) -> None:
        """
        Validates a single value in the list.
        :param value: One of the values in the list.
        """
        self._field.validate(value)


class EmbeddedField(BaseField):

    """Field for embedded models."""

    def __init__(self, model_types, *args, **kwargs):
        self._assign_model_types(model_types)
        super(EmbeddedField, self).__init__(*args, **kwargs)

    def _assign_model_types(self, model_types):
        if not isinstance(model_types, (list, tuple)):
            model_types = (model_types,)

        types = []
        for type_ in model_types:
            if isinstance(type_, six.string_types):
                types.append(_LazyType(type_))
            else:
                types.append(type_)
        self.types = tuple(types)

    def _finish_initialization(self, owner):
        super(EmbeddedField, self)._finish_initialization(owner)
        types = []
        for model_type in self.types:
            if isinstance(model_type, _LazyType):
                types.append(model_type.evaluate(owner))
            else:
                types.append(model_type)

        self.types = tuple(types)

    def validate(self, value):
        super(EmbeddedField, self).validate(value)
        try:
            value.validate()
        except AttributeError:
            pass

    def parse_value(self, value):
        """Parse value to proper model type."""
        if not isinstance(value, dict):
            return value

        embed_type = self._get_embed_type(value, self.types)
        return embed_type(**value)

    def to_struct(self, value):
        return value.to_struct()


class MapField(BaseField):
    """
    Model field that keeps a mapping between two other fields.
    It is basically a dictionary with key and values being separate fields.

    `MapField` is **always not required**. If you want to control number
    of items use validators. You may pass omit_empty so empty lists are not
    included in the to_struct method.

    """
    types = (dict,)

    def __init__(self, key_field: BaseField, value_field: BaseField,
                 **kwargs):
        """
        :param key_field: The field that is responsible for converting and
            validating the keys in this mapping.
        :param value_field: The field that is responsible for converting and
            validating the values in this mapping.
        :param kwargs: Other keyword arguments to the base class.
        """
        super(MapField, self).__init__(**kwargs)
        self._key_field = key_field
        self._value_field = value_field

    def _finish_initialization(self, owner):
        """
        Completes the initialization of the fields, allowing for lazy refs.
        """
        super(MapField, self)._finish_initialization(owner)
        self._key_field._finish_initialization(owner)
        self._value_field._finish_initialization(owner)

    def get_default_value(self) -> any:
        """ Gets the default value for this field """
        default = super(MapField, self).get_default_value()
        if default is None and self.required:
            return dict()
        return default

    def parse_value(self, values: Optional[dict]) -> Optional[dict]:
        """ Parses the given values into a new dict. """
        values = super().parse_value(values)
        if values is None:
            return
        items = [
            (self._key_field.parse_value(key),
             self._value_field.parse_value(value))
            for key, value in values.items()
        ]
        return type(values)(items)  # Preserves OrderedDict

    def to_struct(self, values: Optional[dict]) -> Optional[dict]:
        """ Casts the field values into a dict. """
        items = [
            (self._key_field.to_struct(key),
             self._value_field.to_struct(value))
            for key, value in values.items()
        ]
        return type(values)(items)  # Preserves OrderedDict

    def validate(self, values: Optional[dict]) -> Optional[dict]:
        """
        Validates all keys and values in the map field.
        :param values: The values in the mapping.
        """
        super(MapField, self).validate(values)
        if values is None:
            return
        for key, value in values.items():
            self._key_field.validate(key)
            self._value_field.validate(value)


class _LazyType(object):

    def __init__(self, path):
        self.path = path

    def evaluate(self, base_cls):
        module, type_name = _evaluate_path(self.path, base_cls)
        return _import(module, type_name)


def _evaluate_path(relative_path, base_cls):
    base_module = base_cls.__module__

    modules = _get_modules(relative_path, base_module)

    type_name = modules.pop()
    module = '.'.join(modules)
    if not module:
        module = base_module
    return module, type_name


def _get_modules(relative_path, base_module):
    canonical_path = relative_path.lstrip('.')
    canonical_modules = canonical_path.split('.')

    if not relative_path.startswith('.'):
        return canonical_modules

    parents_amount = len(relative_path) - len(canonical_path)
    parent_modules = base_module.split('.')
    parents_amount = max(0, parents_amount - 1)
    if parents_amount > len(parent_modules):
        raise ValueError("Can't evaluate path '{}'".format(relative_path))
    return parent_modules[:parents_amount * -1] + canonical_modules


def _import(module_name, type_name):
    module = __import__(module_name, fromlist=[type_name])
    try:
        return getattr(module, type_name)
    except AttributeError:
        raise ValueError(
            "Can't find type '{}.{}'.".format(module_name, type_name))


class TimeField(StringField):

    """Time field."""

    types = (datetime.time,)

    def __init__(self, str_format=None, *args, **kwargs):
        """Init.

        :param str str_format: Format to cast time to (if `None` - casting to
            ISO 8601 format).

        """
        self.str_format = str_format
        super(TimeField, self).__init__(*args, **kwargs)

    def to_struct(self, value):
        """Cast `time` object to string."""
        if self.str_format:
            return value.strftime(self.str_format)
        return value.isoformat()

    def parse_value(self, value):
        """Parse string into instance of `time`."""
        if value is None:
            return value
        if isinstance(value, datetime.time):
            return value
        return parse(value).timetz()


class DateField(StringField):

    """Date field."""

    types = (datetime.date,)
    default_format = '%Y-%m-%d'

    def __init__(self, str_format=None, *args, **kwargs):
        """Init.

        :param str str_format: Format to cast date to (if `None` - casting to
            %Y-%m-%d format).

        """
        self.str_format = str_format
        super(DateField, self).__init__(*args, **kwargs)

    def to_struct(self, value):
        """Cast `date` object to string."""
        if self.str_format:
            return value.strftime(self.str_format)
        return value.strftime(self.default_format)

    def toBsonEncodable(self, value: datetime.date) -> BsonEncodable:
        return value

    def parse_value(self, value):
        """Parse string into instance of `date`."""
        if value is None:
            return value
        if isinstance(value, datetime.date):
            return value
        return parse(value).date()


class DateTimeField(StringField):

    """Datetime field."""

    types = (datetime.datetime,)

    def __init__(self, str_format=None, *args, **kwargs):
        """Init.

        :param str str_format: Format to cast datetime to (if `None` - casting
            to ISO 8601 format).

        """
        self.str_format = str_format
        super(DateTimeField, self).__init__(*args, **kwargs)

    def to_struct(self, value):
        """Cast `datetime` object to string."""
        if self.str_format:
            return value.strftime(self.str_format)
        return value.isoformat()

    def parse_value(self, value):
        """Parse string into instance of `datetime`."""
        if isinstance(value, datetime.datetime):
            return value
        if value:
            return parse(value)
        else:
            return None


class GenericField(BaseField):
    """
    Field that supports any kind of value, converting models to their correct
    struct, keeping ordered dictionaries in their original order.
    """
    types = (any,)

    def _validate_against_types(self, value) -> None:
        pass

    def to_struct(self, values: any) -> any:
        """ Casts value to Python structure. """
        from .models import Base
        if isinstance(values, Base):
            return values.to_struct()

        if isinstance(values, (list, tuple)):
            return [self.to_struct(value) for value in values]

        if isinstance(values, dict):
            items = [(self.to_struct(key), self.to_struct(value))
                     for key, value in values.items()]
            return type(values)(items)  # preserves OrderedDict

        return values
