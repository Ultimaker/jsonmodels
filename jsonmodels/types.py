import datetime
from re import Pattern
from typing import Any, Callable, Dict, Generator, List, Literal, Protocol, Tuple, TypedDict, Union, runtime_checkable
from weakref import WeakKeyDictionary

from jsonmodels.models import _CacheKey

Value = Any

JSONObject = Dict[str, "JSONValue"]
JSONValue = Union[None, bool, str, float, int, List["JSONValue"], JSONObject]

# JSONSchema = JSONValue
# JSONSchemaDict = JSONObject

JSONSchemaBasicTypeName = Literal["string"]  | Literal["number"] | Literal["boolean"] | Literal["object"] | Literal["array"] | Literal["null"]
JSONSchemaTypeName = JSONSchemaBasicTypeName | List[JSONSchemaBasicTypeName | Literal["null"]]

class JSONSchemaProperty(TypedDict, total=False):
    type: JSONSchemaTypeName
    format: str
    default: Any
    required: List[str]
    items: JSONSchemaProperty
    description: str
    properties: Dict[str, str | JSONSchemaProperty]
    additionalProperties: bool
    definitions: Dict[str, JSONSchemaProperty]

    minItems: int
    minLength: int
    maxItems: int
    maxLength: int

    minimum: int | float
    exclusiveMinimum: bool

    maximum: int | float
    exclusiveMaximum: bool

    pattern: str
    enum: List[str]

# JSONSchema = JSONSchemaProperty

# BSON compatible types, which can be returned by toBsonEncodable.
BsonEncodable = Union[
    float, str, object, Dict, List, bytes, bool, datetime.datetime, None,
    Pattern, int, bytes
]

@runtime_checkable
class Builder(Protocol):
    def register_type(self, model_type: type[Model], builder: "Builder") -> None:
        ...

    def get_builder(self, model_type: type[Model]) -> "Builder":
        ...

    def count_type(self, model_type: type[Model]) -> int:
        ...

    def build(self) -> str | JSONSchemaProperty:
        ...

    def add_definition(self, builder: "Builder") -> None:
        ...

    def build_definition(self, add_definitions: bool = True) -> JSONSchemaProperty:
        ...

    @property
    def is_definition(self) -> bool:
        ...

    @property
    def type_name(self) -> str:
        ...


@runtime_checkable
class ValidatorObject(Protocol):

    def validate(self, value: Any) -> None:
        ...

    def modify_schema(self, field_schema: JSONSchemaProperty) -> None:
        ...

ValidatorFunction = Callable[[Any], None]
Validator = ValidatorFunction | ValidatorObject

class Field(Protocol):
    types: Tuple[Any, ...]
    memory: WeakKeyDictionary
    required: bool
    validators: List[Validator]
    item_validators: List[Validator]
    help_text: str | None
    nullable: bool
    _default: Any

    @property
    def has_default(self) -> bool:
        ...

    def __set__(self, instance: Model, value: Any) -> None:
        ...

    def __get__(self, instance: Model) -> Any:
        ...

    def _finish_initialization(self, owner: type[Model]) -> None:
        ...

    def to_struct(self, value: Any) -> JSONValue:
        ...

    def structure_name(self, default: str) -> str:
        ...

    def toBsonEncodable(self, value: Any) -> BsonEncodable:
        ...

    def validate_for_object(self, obj: Model) -> None:
        ...

    def parse_value(self, value: Value) -> Any:
        ...

    def validate(self, value: Value) -> None:
        ...

class CollectionField(Field, Protocol):
    def validate_single_value(self, value: Value) -> None:
        ...


Fields = Tuple[str, Field]
FieldsWithNames = Tuple[str, str, Field]

class Model(Protocol):

    # __name__: str
    _cache_key: _CacheKey

    def validate(self) -> None:
        ...

    @classmethod
    def iterate_with_name(cls) -> Generator[FieldsWithNames, None, None]:
        ...

    def to_struct(self) -> JSONValue:
        ...

EmbedType = Union[type[str], type[int], type[float], type[bool], type[list], type[dict], type[Model]]
