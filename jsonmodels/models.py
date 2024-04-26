from typing import Any, Dict, Generator, Tuple, Type, cast

from jsonmodels.types import JSONSchemaProperty

from . import parsers, errors
from .fields import BaseField
from .errors import FieldValidationError, ValidatorError, ValidationError
from .types import Field, JSONSchemaProperty, JSONValue

Values = Dict[str, Any]
Fields = Tuple[str, Field]
FieldsWithNames = Tuple[str, str, Field]


class JsonmodelMeta(type):
    def __new__(cls: Type[JsonmodelMeta], name: str, bases: tuple, attributes: dict) -> type:
        cls.validate_fields(attributes)
        return super(cls, cls).__new__(cls, name, bases, attributes)

    @staticmethod
    def validate_fields(attributes: dict[str, Any]) -> None:
        fields = {
            key: value for key, value in attributes.items()
            if isinstance(value, BaseField)
        }
        taken_names = set()
        for name, field in fields.items():
            structure_name = field.structure_name(name)
            if structure_name in taken_names:
                raise ValueError('Name taken', structure_name, name)
            taken_names.add(structure_name)


class Base(metaclass=JsonmodelMeta):

    """Base class for all models."""

    def __init__(self, **kwargs: Values) -> None:
        self._cache_key = _CacheKey()
        self.populate(**kwargs)

    def populate(self, **values: Values) -> None:
        """Populate values to fields. Skip non-existing."""
        values = values.copy()
        fields = list(self.iterate_with_name())
        for _, structure_name, field in fields:
            if structure_name in values:
                self.set_field(field, structure_name,
                               values.pop(structure_name))
        for name, _, field in fields:
            if name in values:
                self.set_field(field, name, values.pop(name))

    def get_field(self, field_name: str) -> Field:
        """Get field associated with given attribute."""
        for attr_name, field in self:
            if field_name == attr_name:
                return field

        raise errors.FieldNotFound(field_name)

    def set_field(self, field: Field, field_name: str, value: Any) -> None:
        """ Sets the value of a field. """
        try:
            field.__set__(self, value)
        except ValidatorError as error:
            raise FieldValidationError(type(self).__name__, field_name,
                                       value, error)

    def __iter__(self) -> Generator[Fields, None, None]:
        """Iterate through fields and values."""
        for name, field in self.iterate_over_fields():
            yield name, field

    def validate(self) -> None:
        """Explicitly validate all the fields."""
        for name, field in self:
            try:
                field.validate_for_object(self)
            except ValidatorError as error:
                value = field.memory.get(self._cache_key)
                raise FieldValidationError(type(self).__name__, name,
                                           value, error)

    @classmethod
    def iterate_over_fields(cls) -> Generator[Fields, None, None]:
        """Iterate through fields as `(attribute_name, field_instance)`."""
        for attr in dir(cls):
            class_attribute = getattr(cls, attr)
            if isinstance(class_attribute, BaseField):
                yield attr, cast(Field, class_attribute)

    @classmethod
    def iterate_with_name(cls) -> Generator[FieldsWithNames, None, None]:
        """Iterate over fields, but also give `structure_name`.

        Format is `(attribute_name, structure_name, field_instance)`.
        Structure name is name under which value is seen in structure and
        schema (in primitives) and only there.
        """
        for attr_name, field in cls.iterate_over_fields():
            structure_name = field.structure_name(attr_name)
            yield attr_name, structure_name, field

    def to_struct(self) -> JSONValue:
        """Cast model to Python structure."""
        return parsers.to_struct(self)

    @classmethod
    def to_json_schema(cls) -> JSONSchemaProperty:
        """Generate JSON schema for model."""
        return parsers.to_json_schema(cls)

    def __repr__(self) -> str:
        attrs = {}
        for name, _ in self:
            try:
                attr = getattr(self, name)
                if attr is not None:
                    attrs[name] = repr(attr)
            except ValidationError:
                pass

        return '{class_name}({fields})'.format(
            class_name=self.__class__.__name__,
            fields=', '.join(
                '{0[0]}={0[1]}'.format(x) for x in sorted(attrs.items())
            ),
        )

    def __str__(self) -> str:
        return '{name} object'.format(name=self.__class__.__name__)

    def __setattr__(self, name: str, value: Any) -> None:
        try:
            return super(Base, self).__setattr__(name, value)
        except ValidatorError as error:
            raise FieldValidationError(type(self).__name__, name,
                                       value, error)

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False

        for name, _ in self.iterate_over_fields():
            try:
                our = getattr(self, name)
            except ValidationError:
                our = None

            try:
                their = getattr(other, name)
            except ValidationError:
                their = None

            if our != their:
                return False

        return True

    def __ne__(self, other: object) -> bool:
        return not (self == other)


class _CacheKey:
    """Object to identify model in memory."""
