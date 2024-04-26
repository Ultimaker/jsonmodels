"""Builders to generate in memory representation of model and fields tree."""


from collections import defaultdict
from typing import Any, Dict, List, Optional, Set
import six

from . import errors
from .fields import NotSet, Value
from .types import Builder, Field, JSONSchemaProperty, JSONSchemaTypeName, Model


class BaseBuilder:
    def __init__(
        self,
        parent: Optional[Builder] = None,
        nullable: bool = False,
        default: Any = NotSet,
    ) -> None:
        self.parent = parent
        self.types_builders: Dict[type[Model], Builder] = {}
        self.types_count: Dict[type[Model], int] = defaultdict(int)
        self.definitions: Set[Builder] = set()
        self.nullable = nullable
        self.default = default

    @property
    def has_default(self) -> bool:
        return self.default is not NotSet

    def register_type(self, model_type: type[Model], builder: Builder) -> None:
        if self.parent:
            self.parent.register_type(model_type, builder)
            return

        self.types_count[model_type] += 1
        if model_type not in self.types_builders:
            self.types_builders[model_type] = builder

    def get_builder(self, model_type: type[Model]) -> Builder:
        if self.parent:
            return self.parent.get_builder(model_type)

        return self.types_builders[model_type]

    def count_type(self, model_type: type[Model]) -> int:
        if self.parent:
            return self.parent.count_type(model_type)

        return self.types_count[model_type]

    @staticmethod
    def maybe_build(value: Value) -> JSONSchemaProperty | Value:
        return value.build() if isinstance(value, Builder) else value

    def add_definition(self, builder: Builder) -> None:
        if self.parent:
            return self.parent.add_definition(builder)

        self.definitions.add(builder)

    def build_definition(self, add_definitions: bool = True) -> JSONSchemaProperty:
        raise NotImplementedError()

    @property
    def is_definition(self) -> bool:
        raise NotImplementedError()

    @property
    def type_name(self) -> str:
        raise NotImplementedError()


class ObjectBuilder(BaseBuilder):
    def __init__(self, model_type: type[Model], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.properties: Dict[str, str | JSONSchemaProperty] = {}
        self.required: List[str] = []
        self.type = model_type

        self.register_type(self.type, self)

    def add_field(self, name: str, field: Field, schema: str | JSONSchemaProperty) -> None:
        if not isinstance(schema, str):
            _apply_validators_modifications(schema, field)
        if isinstance(schema, dict) and field.help_text:
            schema["description"] = field.help_text
        self.properties[name] = schema
        if field.required:
            self.required.append(name)

    def build(self) -> str | JSONSchemaProperty:
        builder = self.get_builder(self.type)
        if self.is_definition and not self.is_root:
            self.add_definition(builder)
            [self.maybe_build(value) for _, value in self.properties.items()]
            return '#/definitions/{name}'.format(name=self.type_name)
        else:
            return builder.build_definition()

    @property
    def type_name(self) -> str:
        module_name = '{module}.{name}'.format(
            module=self.type.__module__,
            name=self.type.__name__,
        )
        return module_name.replace('.', '_').lower()

    def build_definition(self, add_definitions: bool = True) -> JSONSchemaProperty:
        properties: Dict[str, str | JSONSchemaProperty] = dict(
            (name, self.maybe_build(value))
            for name, value
            in self.properties.items()
        )
        schema: JSONSchemaProperty = {
            'type': 'object',
            'additionalProperties': False,
            'properties': properties,
        }

        if self.required:
            schema['required'] = list(self.required)

        if self.definitions and add_definitions:
            schema['definitions'] = dict(
                (builder.type_name,
                 builder.build_definition(add_definitions=False))
                for builder in self.definitions
            )
        return schema

    @property
    def is_definition(self) -> bool:
        if self.count_type(self.type) > 1:
            return True
        elif self.parent:
            return self.parent.is_definition
        else:
            return False

    @property
    def is_root(self) -> bool:
        return not bool(self.parent)


def _apply_validators_modifications(field_schema: JSONSchemaProperty, field: Field) -> None:
    for validator in field.validators:
        if hasattr(validator, "modify_schema"):
            validator.modify_schema(field_schema)

    # arrays may have separate validators for each item.
    # we should also add those validators to the schema.
    if "items" in field_schema:
        for validator in field.item_validators:
            if hasattr(validator, "modify_schema"):
                validator.modify_schema(field_schema["items"])

class PrimitiveBuilder(BaseBuilder):
    def __init__(self, value_type: type, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.type = value_type

    def build(self) -> JSONSchemaProperty:
        obj_type: JSONSchemaTypeName
        schema: JSONSchemaProperty = {}
        if issubclass(self.type, six.string_types):
            obj_type = 'string'
        elif issubclass(self.type, bool):
            obj_type = 'boolean'
        elif issubclass(self.type, int):
            obj_type = 'number'
        elif issubclass(self.type, float):
            obj_type = 'number'
            schema['format'] = 'float'
        else:
            raise errors.FieldNotSupported(self.type)

        if self.nullable:
            obj_type = [obj_type, 'null']
        schema['type'] = obj_type

        if self.has_default:
            schema["default"] = self.default

        return schema


class ListBuilder(BaseBuilder):

    parent: Builder

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.schemas: list[Builder | JSONSchemaProperty] = []

    def add_type_schema(self, schema: Builder | JSONSchemaProperty) -> None:
        self.schemas.append(schema)

    def build(self) -> str | JSONSchemaProperty:
        schema: JSONSchemaProperty = {'type': 'array'}
        if self.nullable:
            self.add_type_schema({'type': 'null'})  # <- probably a bug

        if self.has_default:
            schema["default"] = [self.to_struct(i) for i in self.default]

        schemas = [self.maybe_build(s) for s in self.schemas]
        if len(schemas) == 1:
            items = schemas[0]
        else:
            items = {'oneOf': schemas}

        schema['items'] = items
        return schema

    @property
    def is_definition(self) -> bool:
        return self.parent.is_definition

    @staticmethod
    def to_struct(item: Value) -> Value:
        from .models import Base
        if isinstance(item, Base):
            return item.to_struct()
        return item


class EmbeddedBuilder(BaseBuilder):
    parent: Builder

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.schemas: list[Builder | JSONSchemaProperty] = []

    def add_type_schema(self, schema: Builder | JSONSchemaProperty) -> None:
        self.schemas.append(schema)

    def build(self) -> JSONSchemaProperty:
        if self.nullable:
            self.add_type_schema({'type': 'null'})

        schemas = [self.maybe_build(schema) for schema in self.schemas]
        if len(schemas) == 1:
            schema = schemas[0]
        else:
            schema = {'oneOf': schemas}

        if self.has_default:
            # The default value of EmbeddedField is expected to be an instance
            # of a subclass of models.Base, thus have `to_struct`
            schema["default"] = self.default.to_struct()

        return schema

    @property
    def is_definition(self) -> bool:
        return self.parent.is_definition
