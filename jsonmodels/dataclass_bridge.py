from dataclasses import dataclass, fields as dataclass_fields
from jsonmodels import fields, parsers, errors
from jsonmodels.errors import FieldValidationError, ValidatorError


@dataclass
class DataClassBridge:
    _cache_key = None   # Mark this class as dataclass-based, not jsonmodel-based.

    def to_struct(self):
        """Cast model to Python structure."""
        return parsers.to_struct(self)

    @classmethod
    def iterate_over_fields(cls):
        """Iterate through fields as `(attribute_name, field_instance)`."""
        for f in dataclass_fields(cls):
            json_key = f.metadata.get("jsonmodel", None)
            yield f.name, json_key

    def get_field(self, field_name: str) -> fields.BaseField:
        """Get field by name."""
        for name, field in self.iterate_over_fields():
            if name == field_name:
                return field
        raise errors.FieldNotFound(field_name)

    @classmethod
    def iterate_with_name(cls):
        """Iterate over fields, but also give `structure_name`.

        Format is `(attribute_name, structure_name, field_instance)`.
        Structure name is name under which value is seen in structure and
        schema (in primitives) and only there.
        """
        for attr_name, field in cls.iterate_over_fields():
            structure_name = field.structure_name(attr_name)
            yield attr_name, structure_name, field

    def __iter__(self):
        """Iterate through fields and values."""
        for name, field in self.iterate_over_fields():
            yield name, field

    def validate(self):
        """Explicitly validate all the fields."""
        for name, field in self:
            try:
                field.validate(getattr(self, name))
            except ValidatorError as error:
                value = getattr(self, name)
                raise FieldValidationError(type(self).__name__, name,
                                           value, error)

    @classmethod
    def to_json_schema(cls):
        """Generate JSON schema for model."""
        return parsers.to_json_schema(cls)
