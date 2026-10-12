from dataclasses import dataclass, fields as dataclass_fields
from jsonmodels import fields, parsers, errors
from jsonmodels.errors import FieldValidationError, ValidatorError, RequiredFieldError
import inspect


@dataclass
class DataClassBridge:
    _cache_key = None   # Mark this class as dataclass-based, not jsonmodel-based.

    def to_struct(self):
        """Cast model to Python structure."""
        return parsers.to_struct(self)

    @classmethod
    def from_struct(cls, struct: dict, target_cls=None):
        """Create an instance and populate it from a struct."""
        values = struct.copy()
        kwargs = {}

        if target_cls is None:
            target_cls = cls

        fields = list(target_cls.iterate_with_name())
        fields = fields + [(field[0], field[0], field[2]) for field in fields]
        for name, structure_name, field in fields:
            if structure_name in values:
                value = values.pop(structure_name)
                try:
                    clean_value = field.parse_value(value)
                except ValidatorError as error:
                    raise FieldValidationError(target_cls.__name__, structure_name, value, error)
                kwargs[name] = clean_value

        for required_field_name in target_cls.__get_required_fields():
            if required_field_name not in kwargs:
                raise FieldValidationError(target_cls.__name__, required_field_name, None, RequiredFieldError())

        return target_cls(**kwargs)

    @classmethod
    def __get_required_fields(cls) -> list[str]:
        # Retrieve the signature of the class constructor
        sig = inspect.signature(cls.__init__)

        required: list[str] = []
        for name, param in sig.parameters.items():
            # Exclude 'self' and variable keyword/positional args (*args, **kwargs)
            if name == 'self' or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            # A field is required if it has no default value
            if param.default is param.empty:
                required.append(name)
        return required

    def populate(self, **values):
        """Populate values to fields. Skip non-existing."""
        values = values.copy()
        fields = list(self.iterate_with_name())
        for name, structure_name, field in fields:
            if structure_name in values:
                clean_value = field.parse_value(values.pop(structure_name))
                setattr(self, name, clean_value)
        for name, _, field in fields:
            if name in values:
                clean_value = field.parse_value(values.pop(name))
                setattr(self, name, clean_value)

    @classmethod
    def iterate_over_fields(cls):
        """Iterate through fields as `(attribute_name, field_instance)`."""
        for f in dataclass_fields(cls):
            json_key = f.metadata.get("jsonmodel", None)
            if json_key is None:
                continue
            if hasattr(json_key, "_finish_initialization"):
                json_key._finish_initialization(cls)
            yield f.name, json_key

    @classmethod
    def get_field(cls, field_name: str) -> fields.BaseField:
        """Get field by name."""
        for name, field in cls.iterate_over_fields():
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
