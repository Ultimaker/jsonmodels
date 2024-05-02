import warnings
from weakref import WeakKeyDictionary

import datetime
import re
import six
from dateutil.parser import parse
from typing import Any, Dict, List, Optional, Tuple, TypeVar, Union, cast

from .collections import ModelCollection
from .errors import AmbiguousTypeError, BadTypeError, RequiredFieldError
from .types import BsonEncodable, EmbedType, Field, JSONValue, Model, PrimitiveTypeInstance, Validator, ValidatorFunction, ValidatorObject, Value


# unique marker for "no default value specified". None is not good enough since
# it is a completely valid default value.
NotSet = object()


class BaseField:

    """Base class for all fields."""

    types: Tuple[Any, ...] = tuple()
    validators: List[Validator] = []

    def __init__(
        self,
        required: bool = False,
        nullable: bool = False,
        help_text: Optional[str] = None,
        validators: Optional[List[Validator]] = None,
        default: Value = NotSet,
        name: Optional[str] = None,
    ) -> None:
        self.memory: WeakKeyDictionary = WeakKeyDictionary()
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
    def has_default(self) -> bool:
        return self._default is not NotSet

    def _assign_validators(self, validators: Validator | List[Validator] | None) -> None:
        if isinstance(validators, list):
            self.validators = validators
        elif validators is not None:
            self.validators = [validators]
        else:
            self.validators = []

    def __set__(self, instance: Model, value: Any) -> None:
        self._finish_initialization(type(instance))
        value = self.parse_value(value)
        self.validate(value)
        self.memory[instance._cache_key] = value

    def __get__(self, instance: Model, owner: Model | None = None) -> Any:
        if instance is None:
            self._finish_initialization(owner)
            return self

        self._finish_initialization(type(instance))

        self._check_value(instance)
        return self.memory[instance._cache_key]

    def _finish_initialization(self, owner: type[Model]) -> None:
        pass

    def _check_value(self, obj: Model) -> None:
        if obj._cache_key not in self.memory:
            self.__set__(obj, self.get_default_value())

    def validate_for_object(self, obj: Model) -> None:
        value = self.__get__(obj)
        self.validate(value)

    def validate(self, value: Any) -> None:
        self._check_types()
        self._validate_against_types(value)
        self._check_against_required(value)
        self._validate_with_custom_validators(value)

    def _check_against_required(self, value: Any) -> None:
        if value is None and self.required:
            raise RequiredFieldError()

    def _validate_against_types(self, value: Any) -> None:
        if value is not None and not isinstance(value, self.types):
            raise BadTypeError(value, self.types, is_list=False)

    def _check_types(self) -> None:
        if self.types is None:
            tpl = 'Field "{type}" is not usable, try different field type.'
            raise ValueError(tpl.format(type=type(self).__name__))

    @staticmethod
    def _get_embed_type(value: Value, models: tuple[EmbedType, ...]) -> EmbedType:
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
            }
            matching_models = [model for model, fields in model_fields.items()
                               if fields.issuperset(value)]

            if len(matching_models) != 1:
                raise AmbiguousTypeError(models)

            # this is the only model that has all given fields
            return matching_models[0]
        return models[0]

    def toBsonEncodable(self, value: Any) -> BsonEncodable:
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

    def to_struct(self, value: Any) -> JSONValue:
        """Cast value to Python structure."""
        return cast(JSONValue, value)

    def parse_value(self, value: Any) -> Any:
        """Parse value from primitive to desired format.

        Each field can parse value to form it wants it to be (like string or
        int).

        """
        return value

    def _validate_with_custom_validators(self, value: Any) -> None:
        if value is None and self.nullable:
            return

        for validator in self.validators:
            try:
                cast(ValidatorObject, validator).validate(value)
            except AttributeError:
                cast(ValidatorFunction, validator)(value)

    def get_default_value(self) -> Any:
        """Get default value for field.

        Each field can specify its default.

        """
        return self._default if self.has_default else None

    def _validate_name(self) -> None:
        if self.name is None:
            return
        if not re.match(r'^[A-Za-z_](([\w\-]*)?\w+)?$', self.name):
            raise ValueError('Wrong name', self.name)

    def structure_name(self, default: str) -> str:
        return self.name if self.name is not None else default

    def structue_name(self, default: str) -> str:
        warnings.warn("`structue_name` is deprecated, please use "
                      "`structure_name`")
        return self.structure_name(default)


class StringField(BaseField):

    """String field."""

    types: Tuple[Any, ...] = six.string_types


class IntField(BaseField):

    """Integer field."""

    types: Tuple[Any, ...] = (int,)

    def parse_value(self, value: Any) -> Any:
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

    types: Tuple[Any, ...] = (float, int)


class BoolField(BaseField):

    """Bool field."""

    types: Tuple[Any, ...] = (bool,)

    def parse_value(self, value: Value) -> Any:
        """Cast value to `bool`."""
        parsed = super(BoolField, self).parse_value(value)
        return bool(parsed) if parsed is not None else None


I = TypeVar("I")


class ListField(BaseField):

    """List field."""

    types: Tuple[Any, ...] = (list, tuple)
    items_types: tuple[EmbedType, ...]
    item_validators: List[Any]

    def __init__(self, items_types: EmbedType | tuple[EmbedType, ...] | List[EmbedType] | None=None, item_validators: Union[Any, List[Any]]=[],
                 omit_empty: bool=False, *args: Any, **kwargs: Any):
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

    def get_default_value(self) -> Any:
        default = super(ListField, self).get_default_value()
        if default is None:
            return ModelCollection(self)
        return default

    def _assign_types(self, items_types: EmbedType | tuple[EmbedType, ...] | List[EmbedType] | None) -> None:
        if items_types:
            if isinstance(items_types, (tuple, list)):
                self.items_types = tuple(items_types)
            else:
                self.items_types = (items_types, )
        else:
            self.items_types = ()

        types = []
        for type_ in self.items_types:
            if isinstance(type_, six.string_types):
                types.append(_LazyType(type_))
            else:
                types.append(type_)
        self.items_types = tuple(types)

    def validate(self, value: Any) -> None:
        super(ListField, self).validate(value)

        for item in value:
            self.validate_single_value(item)

    def validate_single_value(self, value: Any) -> None:
        for validator in self.item_validators:
            try:
                validator.validate(value)
            except AttributeError:
                validator(value)

        if len(self.items_types) == 0:
            return

        if not isinstance(value, self.items_types):
            raise BadTypeError(value, tuple(self.items_types), is_list=True)

    def parse_value(self, values: Any) -> Any:
        """Cast value to proper collection."""
        result = self.get_default_value()

        if not values:
            return result

        if not isinstance(values, list):
            return values

        return [self._cast_value(value) for value in values]

    def _cast_value(self, value: Any) -> Any:
        if isinstance(value, self.items_types):
            return value
        elif isinstance(value, dict):
            model_type = self._get_embed_type(value, self.items_types)
            return model_type(**value)
        else:
            raise BadTypeError(value, tuple(self.items_types), is_list=True)

    def _finish_initialization(self, owner: type[Model]) -> None:
        super(ListField, self)._finish_initialization(owner)

        types = []
        for item_type in self.items_types:
            if isinstance(item_type, _LazyType):
                types.append(item_type.evaluate(owner))
            else:
                types.append(item_type)
        self.items_types = tuple(types)

    def _elem_to_struct(self, value: Value) -> Value | dict[str, Value]:
        try:
            return value.to_struct()
        except AttributeError:
            return value

    def to_struct(self, values: Any) -> JSONValue:
        return [self._elem_to_struct(v) for v in cast(List, values)] \
            if values or not self._omit_empty else None


class DerivedListField(ListField):
    """
    A list field that has another field for its items.
    """

    def __init__(self, field: BaseField | PrimitiveTypeInstance, *args: Any, **kwargs: Any):
        """
        :param field: The field instance that will be in each of the items of the list.
        :param help_text: The help text of the list field.
        :param validators: The validators for the list field.
        """
        # Note: It is a bit of a hack but the signature allows many primitive
        # types even though in reality we only accept BaseField instances.
        # The extra types are for the type checker and our Mypy plugin.
        if not isinstance(field, BaseField):
            raise BadTypeError(field, (BaseField,), is_list=False)

        self._field = field

        fixed_kwargs = kwargs.copy()
        fixed_kwargs["items_types"] = field.types
        fixed_kwargs["item_validators"] = field.validators
        super(DerivedListField, self).__init__(
            *args, **fixed_kwargs,
        )

    def to_struct(self, values: Any) -> JSONValue:
        """
        Converts the list to its output format.
        :param values: The values in the list.
        :return: The converted values.
        """
        return [self._field.to_struct(value) for value in cast(List, values)] \
            if values or not self._omit_empty else None

    def parse_value(self, values: Any) -> Any:
        """
        Converts the list to its internal format.
        :param values: The values in the list.
        :return: The converted values.
        """
        if values is None:
            return None

        try:
            return [self._field.parse_value(value) for value in values]
        except TypeError:
            raise BadTypeError(values, self._field.types, is_list=True)
        return None

    def validate_single_value(self, value: Any) -> None:
        """
        Validates a single value in the list.
        :param value: One of the values in the list.
        """
        self._field.validate(value)


class EmbeddedField(BaseField):

    """Field for embedded models."""

    def __init__(self, model_types: EmbedType | str | tuple[EmbedType | str, ...], *args: Any, **kwargs: Any) -> None:
        self._assign_model_types(model_types)
        super(EmbeddedField, self).__init__(*args, **kwargs)

    def _assign_model_types(self, model_types: EmbedType | str | tuple[EmbedType | str, ...]) -> None:
        if not isinstance(model_types, (list, tuple)):
            model_types = (model_types,)

        types: List[EmbedType | _LazyType] = []
        for type_ in model_types:
            if isinstance(type_, six.string_types):
                types.append(_LazyType(type_))
            else:
                types.append(cast(EmbedType, type_))
        self.types = tuple(types)

    def _finish_initialization(self, owner: type[Model]) -> None:
        super(EmbeddedField, self)._finish_initialization(owner)
        types = []
        for model_type in self.types:
            if isinstance(model_type, _LazyType):
                types.append(model_type.evaluate(owner))
            else:
                types.append(model_type)

        self.types = tuple(types)

    def validate(self, value: Any) -> None:
        super(EmbeddedField, self).validate(value)
        try:
            value.validate()
        except AttributeError:
            pass

    def parse_value(self, value: Any) -> Any:
        """Parse value to proper model type."""
        if not isinstance(value, dict):
            return cast(EmbedType, value)

        embed_type = self._get_embed_type(value, self.types)
        return embed_type(**value)

    def to_struct(self, value: Any) -> JSONValue:
        return cast(Model, value).to_struct()


class MapField(BaseField):
    """
    Model field that keeps a mapping between two other fields.
    It is basically a dictionary with key and values being separate fields.

    `MapField` is **always not required**. If you want to control number
    of items use validators. You may pass omit_empty so empty lists are not
    included in the to_struct method.

    """
    types: Tuple[Any, ...] = (dict,)

    def __init__(self, key_field: BaseField | PrimitiveTypeInstance, value_field: BaseField | PrimitiveTypeInstance,
                 **kwargs: Any):
        """
        :param key_field: The field that is responsible for converting and
            validating the keys in this mapping.
        :param value_field: The field that is responsible for converting and
            validating the values in this mapping.
        :param kwargs: Other keyword arguments to the base class.
        """
        super(MapField, self).__init__(**kwargs)

        # Note: It is a bit of a hack but the signature allows many primitive
        # types even though in reality we only accept BaseField instances.
        # The extra types are for the type checker and our Mypy plugin.
        if not isinstance(key_field, BaseField):
            raise BadTypeError(key_field, (BaseField,), is_list=False)
        self._key_field = key_field

        if not isinstance(value_field, BaseField):
            raise BadTypeError(value_field, (BaseField,), is_list=False)
        self._value_field = value_field

    def _finish_initialization(self, owner: type[Model]) -> None:
        """
        Completes the initialization of the fields, allowing for lazy refs.
        """
        super(MapField, self)._finish_initialization(owner)
        self._key_field._finish_initialization(owner)
        self._value_field._finish_initialization(owner)

    def get_default_value(self) -> Any:
        """ Gets the default value for this field """
        default = super(MapField, self).get_default_value()
        if default is None and self.required:
            return dict()
        return default

    def parse_value(self, values: Any) -> Any:
        """ Parses the given values into a new dict. """
        values = super().parse_value(values)
        if values is None:
            return None
        items = [
            (self._key_field.parse_value(key),
             self._value_field.parse_value(value))
            for key, value in values.items()
        ]
        return type(values)(items)  # Preserves OrderedDict

    def to_struct(self, values: Any) -> JSONValue:
        """ Casts the field values into a dict. """
        items = [
            (self._key_field.to_struct(key),
             self._value_field.to_struct(value))
            for key, value in cast(Dict, values).items()
        ]
        return cast(JSONValue, type(values)(items))  # Preserves OrderedDict

    def validate(self, values: Any) -> None:
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


class _LazyType:
    def __init__(self, path: str) -> None:
        self.path = path

    def evaluate(self, base_cls: type[Model]) -> Any:
        module, type_name = _evaluate_path(self.path, base_cls)
        return _import(module, type_name)


def _evaluate_path(relative_path: str, base_cls: type[Model]) -> tuple[Any, str]:
    base_module = base_cls.__module__

    modules = _get_modules(relative_path, base_module)

    type_name = modules.pop()
    module = '.'.join(modules)
    if not module:
        module = base_module
    return module, type_name


def _get_modules(relative_path: str, base_module: str) -> Any:
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


def _import(module_name: str, type_name: str) -> Any:
    module = __import__(module_name, fromlist=[type_name])
    try:
        return getattr(module, type_name)
    except AttributeError:
        raise ValueError(
            "Can't find type '{}.{}'.".format(module_name, type_name))


class TimeField(StringField):

    """Time field."""

    types: Tuple[Any, ...] = (datetime.time,)

    def __init__(
        self, str_format: Optional[str] = None, *args: Any, **kwargs: Any
    ) -> None:
        """Init.

        :param str str_format: Format to cast time to (if `None` - casting to
            ISO 8601 format).

        """
        self.str_format = str_format
        super(TimeField, self).__init__(*args, **kwargs)

    def to_struct(self, value: Any) -> JSONValue:
        """Cast `time` object to string."""
        datetime_value = cast(datetime.time, value)
        if self.str_format:
            return datetime_value.strftime(self.str_format)
        return datetime_value.isoformat()

    def parse_value(self, value: Any) -> Any:
        """Parse string into instance of `time`."""
        if value is None:
            return value
        if isinstance(value, datetime.time):
            return value
        return parse(value).timetz()


class DateField(StringField):

    """Date field."""

    types: Tuple[Any, ...] = (datetime.date,)
    default_format = '%Y-%m-%d'

    def __init__(
        self, str_format: Optional[str] = None, *args: Any, **kwargs: Any
    ) -> None:
        """Init.

        :param str str_format: Format to cast date to (if `None` - casting to
            %Y-%m-%d format).

        """
        self.str_format = str_format
        super(DateField, self).__init__(*args, **kwargs)

    def to_struct(self, value: Any) -> JSONValue:
        """Cast `date` object to string."""
        date_value = cast(datetime.date, value)
        if self.str_format:
            return date_value.strftime(self.str_format)
        return date_value.strftime(self.default_format)

    def parse_value(self, value: Any) -> Any:
        """Parse string into instance of `date`."""
        if value is None:
            return value
        if isinstance(value, datetime.date):
            return value
        return parse(value).date()


class DateTimeField(StringField):

    """Datetime field."""

    types: Tuple[Any, ...] = (datetime.datetime,)

    def __init__(
        self, str_format: Optional[str] = None, *args: Any, **kwargs: Any
    ) -> None:
        """Init.

        :param str str_format: Format to cast datetime to (if `None` - casting
            to ISO 8601 format).

        """
        self.str_format = str_format
        super(DateTimeField, self).__init__(*args, **kwargs)

    def to_struct(self, value: Any) -> JSONValue:
        """Cast `datetime` object to string."""
        datetime_value = cast(datetime.datetime, value)
        if self.str_format:
            return datetime_value.strftime(self.str_format)
        return datetime_value.isoformat()

    def toBsonEncodable(self, value: Any) -> BsonEncodable:
        """
        Keep datetime object a datetime object, since pymongo supports that.
        """
        if not isinstance(value, self.types):
            raise BadTypeError(value, self.types, is_list=False)
        return cast(BsonEncodable, value)

    def parse_value(self, value: Any) -> Any:
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
    types: Tuple[Any, ...] = (any,)

    def _validate_against_types(self, value: Value) -> None:
        pass

    def to_struct(self, values: Any) -> JSONValue:
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

        return cast(JSONValue, values)
