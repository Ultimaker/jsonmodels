import pytest

from jsonmodels import models, fields, validators, errors, builders
from jsonmodels.utilities import compare_schemas

from .utilities import get_fixture


def test_model1():

    class Person(models.Base):

        name = fields.StringField(required=True)
        surname = fields.StringField(required=True)
        age = fields.IntField()

    alan = Person()
    schema = alan.to_json_schema()

    pattern = get_fixture('schema1.json')
    assert compare_schemas(pattern, schema) is True


def test_model2():

    class Car(models.Base):

        brand = fields.StringField(required=True)
        registration = fields.StringField(required=True)

    class Toy(models.Base):

        name = fields.StringField(required=True)

    class Kid(models.Base):

        name = fields.StringField(required=True)
        surname = fields.StringField(required=True)
        age = fields.IntField()
        toys = fields.ListField(Toy)

    class Person(models.Base):

        name = fields.StringField(required=True)
        surname = fields.StringField(required=True)
        age = fields.IntField()
        kids = fields.ListField(Kid,
                                default=[Kid(name="Name", surname="Surname")])
        car = fields.EmbeddedField(Car)

    chuck = Person()
    schema = chuck.to_json_schema()

    pattern = get_fixture('schema2.json')
    assert compare_schemas(pattern, schema) is True


def test_model3():

    class Viper(models.Base):

        brand = fields.StringField()
        capacity = fields.FloatField()

    class Lamborghini(models.Base):

        brand = fields.StringField()
        velocity = fields.FloatField()

    class PC(models.Base):

        name = fields.StringField()
        ports = fields.StringField()

    class Laptop(models.Base):

        name = fields.StringField()
        battery_voltage = fields.FloatField()

    class Tablet(models.Base):

        name = fields.StringField()
        os = fields.StringField()

    class Person(models.Base):

        name = fields.StringField(required=True)
        surname = fields.StringField(required=True)
        age = fields.IntField()
        car = fields.EmbeddedField([Viper, Lamborghini])
        computer = fields.ListField([PC, Laptop, Tablet])
        meta = fields.GenericField()

    schema = Person.to_json_schema()

    pattern = get_fixture('schema3.json')
    assert compare_schemas(pattern, schema) is True


def test_model_with_constructors():

    class Car(models.Base):
        brand = fields.StringField(required=True)
        registration = fields.StringField(required=True)

        def __init__(self, some_value):
            pass

    class Toy(models.Base):
        name = fields.StringField(required=True)

        def __init__(self, some_value):
            pass

    class Kid(models.Base):
        name = fields.StringField(required=True)
        surname = fields.StringField(required=True)
        age = fields.IntField()
        toys = fields.ListField(Toy)

        def __init__(self, name="Name", surname="Surname"):
            super().__init__(name=name, surname=surname)

    class Person(models.Base):
        name = fields.StringField(required=True)
        surname = fields.StringField(required=True)
        age = fields.IntField()
        kids = fields.ListField(Kid, default=[Kid()])
        car = fields.EmbeddedField(Car)

        def __init__(self, some_value):
            pass

    schema = Person.to_json_schema()
    pattern = get_fixture('schema2.json')
    assert compare_schemas(pattern, schema) is True


def test_datetime_fields():

    class Event(models.Base):

        time = fields.TimeField()
        date = fields.DateField()
        end = fields.DateTimeField()

    schema = Event.to_json_schema()

    pattern = get_fixture('schema4.json')
    assert compare_schemas(pattern, schema) is True


def test_bool_field():

    class Person(models.Base):

        has_childen = fields.BoolField()

    schema = Person.to_json_schema()

    pattern = get_fixture('schema5.json')
    assert compare_schemas(pattern, schema) is True


def test_unsupported_field():

    class NewField(fields.BaseField):

        pass

    class Person(models.Base):

        some_property = NewField()

    with pytest.raises(errors.FieldNotSupported):
        Person.to_json_schema()


def test_validators_can_modify_schema():

    class ClassBasedValidator(object):

        def validate(self, value):
            raise RuntimeError()

        def modify_schema(self, field_schema):
            field_schema['some'] = 'unproper value'

    def function_validator(value):
        raise RuntimeError()

    class Person(models.Base):

        name = fields.StringField(validators=ClassBasedValidator())
        surname = fields.StringField(validators=function_validator)

        friend_names = fields.ListField(
            str, item_validators=ClassBasedValidator()
        )
        friend_surnames = fields.ListField(
            str, item_validators=function_validator
        )

    for person in [Person, Person()]:
        schema = person.to_json_schema()

        pattern = get_fixture('schema6.json')
        assert compare_schemas(pattern, schema) is True


def test_min_validator():

    class Person(models.Base):

        name = fields.StringField()
        surname = fields.StringField()
        age = fields.IntField(validators=validators.Min(18))

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_min.json')
    assert compare_schemas(pattern, schema)


def test_min_validator_with_exclusive():

    class Person(models.Base):

        name = fields.StringField()
        surname = fields.StringField()
        age = fields.IntField(validators=validators.Min(18, True))

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_min_exclusive.json')
    assert compare_schemas(pattern, schema)


def test_max_validator():

    class Person(models.Base):

        name = fields.StringField()
        surname = fields.StringField()
        age = fields.IntField(validators=validators.Max(18))

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_max.json')
    assert compare_schemas(pattern, schema)


def test_max_validator_with_exclusive():

    class Person(models.Base):

        name = fields.StringField()
        surname = fields.StringField()
        age = fields.IntField(validators=validators.Max(18, True))

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_max_exclusive.json')
    assert compare_schemas(pattern, schema)


def test_regex_validator():

    class Person(models.Base):

        name = fields.StringField(
            validators=validators.Regex('^some pattern$'))

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_pattern.json')
    assert compare_schemas(pattern, schema)


def test_regex_validator_when_ecma_regex_given():

    class Person(models.Base):

        name = fields.StringField(
            validators=validators.Regex('/^some pattern$/'))

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_pattern.json')
    assert compare_schemas(pattern, schema)


def test_regex_validator_with_flag():

    class Person(models.Base):

        name = fields.StringField(
            validators=validators.Regex(
                '^some pattern$', ignorecase=True))

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_pattern_flag.json')
    assert compare_schemas(pattern, schema)


def test_length_validator_min():

    class Person(models.Base):

        name = fields.StringField(validators=validators.Length(5))
        surname = fields.StringField()
        age = fields.IntField()

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_length_min.json')
    assert compare_schemas(pattern, schema)


def test_length_validator():

    class Person(models.Base):

        name = fields.StringField(validators=validators.Length(5, 20))
        surname = fields.StringField()
        age = fields.IntField()

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_length.json')
    assert compare_schemas(pattern, schema)


def test_length_validator_list():

    class People(models.Base):
        min_max_len = fields.ListField(str, validators=validators.Length(2, 4))
        min_len = fields.ListField(str, validators=validators.Length(2))
        max_len = fields.ListField(str, validators=validators.Length(4))
        item_validator_int = fields.ListField(
            int, item_validators=[validators.Min(10), validators.Max(20)]
        )
        item_validator_str = fields.ListField(
            str, item_validators=[validators.Length(10, 20),
                                  validators.Regex(r"\w+")],
            validators=[validators.Length(1, 2)],
        )
        surname = fields.StringField()

    schema = People.to_json_schema()

    pattern = get_fixture('schema_length_list.json')
    assert compare_schemas(pattern, schema)


def test_max_only_validator():

    class Person(models.Base):

        name = fields.StringField(
            validators=validators.Length(maximum_value=20)
        )
        surname = fields.StringField()
        age = fields.IntField()

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_length_max.json')
    assert compare_schemas(pattern, schema)


def test_schema_for_list_and_primitives():

    class Event(models.Base):

        time = fields.TimeField()
        date = fields.DateField()
        end = fields.DateTimeField()

    class Person(models.Base):

        names = fields.ListField(
            [str, int, float, bool, Event],
            help_text="A list of names.",
        )

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_with_list.json')
    assert compare_schemas(pattern, schema)


def test_schema_for_unsupported_primitive():

    class Person(models.Base):

        names = fields.ListField([str, object])

    with pytest.raises(errors.FieldNotSupported):
        Person.to_json_schema()


def test_enum_validator():
    class Person(models.Base):
        handness = fields.StringField(
            help_text="The person's favorite hand.",
            validators=validators.Enum('left', 'right')
        )

    schema = Person.to_json_schema()
    pattern = get_fixture('schema_enum.json')
    assert compare_schemas(pattern, schema)


def test_default_value():

    class Pet(models.Base):
        kind = fields.StringField(default="Dog")

    class Person(models.Base):
        name = fields.StringField(default="John Doe")
        age = fields.IntField(default=18)
        pet = fields.EmbeddedField(Pet, default=Pet(kind="Cat"))
        nicknames = fields.ListField(
            items_types=(str,), default=["yo", "dawg"])
        profession = fields.StringField(default=None)

    schema = Person.to_json_schema()
    pattern = get_fixture('schema_with_defaults.json')

    assert compare_schemas(pattern, schema)


def test_primitives():
    cases = (
        (str, "string"),
        (bool, "boolean"),
        (int, "number"),
    )
    for pytpe, jstype in cases:
        b = builders.PrimitiveBuilder(pytpe)
        assert b.build() == {"type": jstype}
        b = builders.PrimitiveBuilder(pytpe, nullable=True)
        assert b.build() == {"type": [jstype, "null"]}
        b = builders.PrimitiveBuilder(pytpe, nullable=True, default=0)
        assert b.build() == {"type": [jstype, "null"], "default": 0}

    b = builders.PrimitiveBuilder(float)
    assert b.build() == {"type": "number", "format": "float"}
    b = builders.PrimitiveBuilder(float, nullable=True)
    assert b.build() == {"type": ["number", "null"], "format": "float"}
    b = builders.PrimitiveBuilder(float, nullable=True, default=0)
    assert b.build() == {"type": ["number", "null"], "default": 0,
                         "format": "float"}


def test_map_field():
    class FaultData(models.Base):
        data = fields.MapField(
            key_field=fields.StringField(),
            value_field=fields.StringField()
        )

    schema = FaultData.to_json_schema()
    pattern = get_fixture('schema_map.json')

    assert compare_schemas(pattern, schema)
