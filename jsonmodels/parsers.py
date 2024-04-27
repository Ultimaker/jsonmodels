"""Parsers to change model structure into different ones."""
import inspect
from typing import Any, cast

from . import builders, errors, fields
from .types import Builder, Field, JSONSchemaProperty, JSONSchemaTypeName, JSONValue, Model


def to_struct(model: Model) -> JSONValue:
    """Cast instance of model to python structure."""
    model.validate()

    resp = {}
    for _, name, field in model.iterate_with_name():
        value = field.__get__(model)
        if value is None:
            continue

        value = field.to_struct(value)
        if value is not None:
            resp[name] = value
    return resp


def to_json_schema(cls: Any) -> JSONSchemaProperty:
    """Generate JSON schema for given class."""
    builder = build_json_schema(cls)
    return cast(JSONSchemaProperty, builder.build())


def build_json_schema(value: Any, parent_builder: Builder | None = None) -> Builder:
    from .models import Base

    cls = value if inspect.isclass(value) else value.__class__
    if issubclass(cls, Base):
        return build_json_schema_object(cls, parent_builder)
    else:
        return build_json_schema_primitive(cls, parent_builder)


def build_json_schema_object(cls: type[Model], parent_builder: Builder | None = None) -> builders.ObjectBuilder:
    builder = builders.ObjectBuilder(cls, parent_builder)
    if builder.count_type(builder.type) > 1:
        return builder
    for _, name, field in cls.iterate_with_name():
        if isinstance(field, fields.EmbeddedField):
            builder.add_field(name, field, _parse_embedded(field, builder))
        elif isinstance(field, fields.ListField):
            builder.add_field(name, field, _parse_list(field, builder))
        else:
            builder.add_field(name, field, _create_primitive_field_schema(field))
    return builder


def _parse_list(field: fields.ListField, parent_builder: Builder | None) -> str | JSONSchemaProperty:
    builder = builders.ListBuilder(
        parent_builder, field.nullable, default=field._default)
    for type in field.items_types:
        builder.add_type_schema(build_json_schema(type, builder))
    return builder.build()


def _parse_embedded(field: fields.EmbeddedField, parent_builder: Builder | None) -> str | JSONSchemaProperty:
    builder = builders.EmbeddedBuilder(
        parent_builder, field.nullable, default=field._default)
    for type in field.types:
        builder.add_type_schema(build_json_schema(type, builder))
    return builder.build()


def build_json_schema_primitive(cls: type, parent_builder: Builder | None) -> Builder:
    builder = builders.PrimitiveBuilder(cls, parent_builder)
    return builder


def _create_primitive_field_schema(field: Field) -> JSONSchemaProperty:
    schema: JSONSchemaProperty = {'type': _get_schema_type(field)}

    if isinstance(field, fields.FloatField):
        schema['format'] = 'float'
    elif isinstance(field, fields.DateField):
        schema['format'] = 'date'
    elif isinstance(field, fields.DateTimeField):
        schema['format'] = 'date-time'

    if field.has_default:
        schema["default"] = field._default

    return schema


def _get_schema_type(field: Field) -> JSONSchemaTypeName:
    obj_type: JSONSchemaTypeName
    if isinstance(field, fields.StringField):
        obj_type = 'string'
    elif isinstance(field, fields.IntField):
        obj_type = 'number'
    elif isinstance(field, fields.FloatField):
        obj_type = 'number'
    elif isinstance(field, fields.BoolField):
        obj_type = 'boolean'
    elif isinstance(field, fields.GenericField):
        obj_type = 'object'
    else:
        raise errors.FieldNotSupported(type(field))
    if field.nullable:
        return [obj_type, 'null']
    return obj_type
