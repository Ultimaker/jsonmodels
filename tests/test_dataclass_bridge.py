import pytest

import datetime
from dataclasses import dataclass, field

from jsonmodels import fields, errors, models, validators
from jsonmodels.utilities import compare_schemas
from jsonmodels.dataclass_bridge import DataClassBridge

from .utilities import get_fixture


def test_model1():

    # class Person(models.Base):
    #     name = fields.StringField()
    #     surname = fields.StringField()
    #     age = fields.IntField()

    @dataclass
    class Person(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField()})

    alan = Person()

    alan.name = 'Alan'
    alan.surname = 'Wake'
    alan.age = 34
    assert {'name': 'Alan', 'surname': 'Wake', 'age': 34} == alan.to_struct()


def test_required():

    @dataclass
    class Person(DataClassBridge):

        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField()})

    alan = Person()
    with pytest.raises(errors.ValidationError):
        alan.validate()

    alan.name = 'Chuck'
    alan.validate()


def test_list_field_types():

    @dataclass
    class Wheel(DataClassBridge):
        pass

    @dataclass
    class Wheel2(DataClassBridge):
        pass

    @dataclass
    class Car(DataClassBridge):
        wheels: list[Wheel] = field(default_factory=list, metadata={'jsonmodel': fields.ListField(items_types=[Wheel])})

    viper = Car()

    viper.wheels.append(Wheel())
    viper.wheels.append(Wheel())
    viper.validate()

    # This test below now becomes a static type error.

    # with pytest.raises(errors.ValidationError):
    #     viper.wheels.append(Wheel2)
    assert viper.to_struct() == {'wheels': [{}, {}]}


def test_list_omit_empty():

    @dataclass
    class Car(DataClassBridge):
        wheels: list[str] = field(default_factory=list,
                                  metadata={'jsonmodel': fields.ListField(items_types=[str], omit_empty=True)})

    viper = Car()
    assert viper.to_struct() == {}


def test_embedded_model():

    @dataclass
    class Secondary(DataClassBridge):

        data: int | None = field(default=None, metadata={'jsonmodel': fields.IntField()})

    @dataclass
    class Primary(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        secondary: Secondary | None = field(default=None, metadata={'jsonmodel': fields.EmbeddedField(Secondary)})

    entity = Primary()
    assert entity.secondary is None
    entity.name = 'chuck'
    entity.secondary = Secondary()
    entity.secondary.data = 42

    # with pytest.raises(errors.ValidationError):
    #     entity.secondary = 'something different'

    entity.validate()
    assert entity.to_struct() == {'name': 'chuck', 'secondary': {'data': 42}}

    entity.secondary = None
    entity.validate()
    assert entity.to_struct() == {'name': 'chuck'}


def test_help_text():

    @dataclass
    class Person(DataClassBridge):

        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(help_text='Name of person.')})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField(help_text='Age of person.')})

    person = Person()
    assert person.get_field('name').help_text == 'Name of person.'
    assert person.get_field('age').help_text == 'Age of person.'


def test_to_struct_nested_1():

    @dataclass
    class Car(DataClassBridge):
        brand: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})

    @dataclass
    class ParkingPlace(DataClassBridge):
        location: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        car: Car | None = field(default=None, metadata={'jsonmodel': fields.EmbeddedField(Car)})

    place = ParkingPlace()
    place.location = 'never never land'

    pattern: dict = {
        'location': 'never never land',
    }
    assert pattern == place.to_struct()

    place.car = Car()
    pattern['car'] = {}
    assert pattern == place.to_struct()

    place.car.brand = 'Fiat'
    pattern['car']['brand'] = 'Fiat'
    assert pattern == place.to_struct()


def test_to_struct_nested_2():

    @dataclass
    class Viper(DataClassBridge):

        serial: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})

    @dataclass
    class Lamborghini(DataClassBridge):
        serial: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})

    @dataclass
    class Parking(DataClassBridge):
        location: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        cars: list[DataClassBridge] = field(default_factory=list,
                                            metadata={'jsonmodel': fields.ListField(items_types=[Viper, Lamborghini])})

    parking = Parking()
    pattern: dict = {'cars': []}
    assert pattern == parking.to_struct()

    parking.location = 'somewhere'
    pattern['location'] = 'somewhere'
    assert pattern == parking.to_struct()

    viper = Viper()
    viper.serial = '12345'
    parking.cars.append(viper)
    pattern['cars'].append({'serial': '12345'})
    assert pattern == parking.to_struct()

    parking.cars.append(Viper())
    pattern['cars'].append({})
    assert pattern == parking.to_struct()

    lamborghini = Lamborghini()
    lamborghini.serial = '54321'
    parking.cars.append(lamborghini)
    pattern['cars'].append({'serial': '54321'})
    assert pattern == parking.to_struct()


def test_to_struct_with_non_models_types():

    @dataclass
    class Person(DataClassBridge):
        names: list[str] = field(default_factory=list, metadata={'jsonmodel': fields.ListField(str)})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})

    person = Person()
    pattern: dict = {'names': []}

    assert pattern == person.to_struct()

    person.surname = 'Norris'
    pattern['surname'] = 'Norris'
    assert pattern == person.to_struct()

    person.names.append('Chuck')
    pattern['names'].append('Chuck')
    assert pattern == person.to_struct()

    person.names.append('Testa')
    pattern['names'].append('Testa')
    assert pattern == person.to_struct()


def test_to_struct_with_multi_non_models_types():

    @dataclass
    class Person(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        mix: list[str | float] = field(default_factory=list, metadata={'jsonmodel': fields.ListField((str, float))})

    person = Person()
    pattern: dict = {'mix': []}
    assert pattern == person.to_struct()

    person.mix.append('something')
    pattern['mix'].append('something')
    assert pattern == person.to_struct()

    person.mix.append(42.0)
    pattern['mix'].append(42.0)
    assert pattern == person.to_struct()

    person.mix.append('different')
    pattern['mix'].append('different')
    assert pattern == person.to_struct()


def test_list_to_struct():

    @dataclass
    class Cat(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        breed: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})

    @dataclass
    class Dog(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField()})

    @dataclass
    class Person(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        pets: list[DataClassBridge] = field(default_factory=list,
                                            metadata={'jsonmodel': fields.ListField(items_types=[Cat, Dog])})

    cat = Cat(name='Garfield')
    dog = Dog(name='Dogmeat', age=9)

    person = Person(name='Johny', surname='Bravo', pets=[cat, dog])
    pattern = {
        'surname': 'Bravo',
        'name': 'Johny',
        'pets': [
            {'name': 'Garfield'},
            {'age': 9, 'name': 'Dogmeat'}
        ]
    }
    assert pattern == person.to_struct()


# With dataclasses and static typing we don't have any automatic
# type conversion so this test becomes a static type error.

# def test_to_struct_time():
#
#     class Clock(models.Base):
#         time = fields.TimeField()
#
#     clock = Clock()
#     clock.time = '12:03:34'
#
#     pattern = {
#         'time': '12:03:34'
#     }
#     assert pattern == clock.to_struct()

def test_mixed_nested_models():

    class Car(models.Base):
        brand = fields.StringField()

    @dataclass
    class ParkingPlace(DataClassBridge):
        location: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        car: Car | None = field(default=None, metadata={'jsonmodel': fields.EmbeddedField(Car)})

    place = ParkingPlace()
    place.location = 'never never land'

    pattern: dict = {
        'location': 'never never land',
    }
    assert pattern == place.to_struct()

    place.car = Car()
    pattern['car'] = {}
    assert pattern == place.to_struct()

    place.car.brand = 'Fiat'
    pattern['car']['brand'] = 'Fiat'
    assert pattern == place.to_struct()


def test_mixed_nested_models2():

    @dataclass
    class Car(DataClassBridge):
        brand: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})

    class ParkingPlace(models.Base):
        location = fields.StringField()
        car = fields.EmbeddedField(Car)

    place = ParkingPlace()
    place.location = 'never never land'

    pattern: dict = {
        'location': 'never never land',
    }
    assert pattern == place.to_struct()

    place.car = Car()
    pattern['car'] = {}
    assert pattern == place.to_struct()

    place.car.brand = 'Fiat'
    pattern['car']['brand'] = 'Fiat'
    assert pattern == place.to_struct()


def test_schema_model1():

    @dataclass
    class Person(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField()})

    alan = Person()
    schema = alan.to_json_schema()

    pattern = get_fixture('schema1.json')
    assert compare_schemas(pattern, schema) is True


def test_schema_model2():

    @dataclass
    class Car(DataClassBridge):
        brand: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        registration: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})

    @dataclass
    class Toy(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})

    @dataclass
    class Kid(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField()})
        toys: list[Toy] | None = field(default_factory=list, metadata={'jsonmodel': fields.ListField(Toy)})

    @dataclass
    class Person(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField()})
        kids: list[Kid] | None = field(default_factory=list,
                                       metadata={'jsonmodel': fields.ListField(Kid, default=[
                                           Kid(name="Name", surname="Surname")])})
        car: Car | None = field(default=None, metadata={'jsonmodel': fields.EmbeddedField(Car)})

    chuck = Person()
    schema = chuck.to_json_schema()

    pattern = get_fixture('schema2.json')
    print("Pattern: " + repr(pattern))
    print("Schema: " + repr(schema))
    assert compare_schemas(pattern, schema)


def test_schema_model3():

    @dataclass
    class Viper(DataClassBridge):
        brand: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        capacity: float | None = field(default=None, metadata={'jsonmodel': fields.FloatField()})

    @dataclass
    class Lamborghini(DataClassBridge):
        brand: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        velocity: float | None = field(default=None, metadata={'jsonmodel': fields.FloatField()})

    @dataclass
    class PC(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        ports: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})

    @dataclass
    class Laptop(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        battery_voltage: float | None = field(default=None, metadata={'jsonmodel': fields.FloatField()})

    @dataclass
    class Tablet(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        os: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})

    @dataclass
    class Person(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField(required=True)})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField()})
        car: list[Viper | Lamborghini] | None = field(default_factory=list,
                                                      metadata={'jsonmodel': fields.EmbeddedField([
                                                          Viper, Lamborghini])})
        computer: list[PC | Laptop | Tablet] | None = field(default_factory=list,
                                                            metadata={'jsonmodel': fields.ListField([
                                                                PC, Laptop, Tablet])})
        meta: dict | None = field(default=None, metadata={'jsonmodel': fields.GenericField()})

    schema = Person.to_json_schema()

    pattern = get_fixture('schema3.json')
    assert compare_schemas(pattern, schema) is True


def test_schema_datetime_fields():
    @dataclass
    class Event(DataClassBridge):
        time: datetime.time | None = field(default=None, metadata={'jsonmodel': fields.TimeField()})
        date: datetime.date | None = field(default=None, metadata={'jsonmodel': fields.DateField()})
        end: datetime.datetime | None = field(default=None, metadata={'jsonmodel': fields.DateTimeField()})

    schema = Event.to_json_schema()

    pattern = get_fixture('schema4.json')
    assert compare_schemas(pattern, schema) is True


def test_schema_bool_field():
    @dataclass
    class Person(DataClassBridge):
        has_childen: bool | None = field(default=None, metadata={'jsonmodel': fields.BoolField()})

    schema = Person.to_json_schema()

    pattern = get_fixture('schema5.json')
    assert compare_schemas(pattern, schema) is True


def test_validators_can_modify_schema():

    class ClassBasedValidator(object):

        def validate(self, value):
            raise RuntimeError()

        def modify_schema(self, field_schema):
            field_schema['some'] = 'unproper value'

    def function_validator(value):
        raise RuntimeError()

    @dataclass
    class Person(DataClassBridge):

        name: str | None = field(default=None,
                                 metadata={'jsonmodel': fields.StringField(validators=ClassBasedValidator())})
        surname: str | None = field(default=None,
                                    metadata={'jsonmodel': fields.StringField(validators=function_validator)})

        friend_names: list[str] | None = field(default_factory=list,
                                               metadata={'jsonmodel':
                                                         fields.ListField(str, item_validators=ClassBasedValidator())})
        friend_surnames: list[str] | None = field(default_factory=list,
                                                  metadata={'jsonmodel':
                                                            fields.ListField(str, item_validators=function_validator)})

    for person in [Person, Person()]:
        schema = person.to_json_schema()

        pattern = get_fixture('schema6.json')
        assert compare_schemas(pattern, schema) is True


def test_min_validator():

    @dataclass
    class Person(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField(validators=validators.Min(18))})

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_min.json')
    assert compare_schemas(pattern, schema)


def test_min_validator_with_exclusive():

    @dataclass
    class Person(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        age: int | None = field(default=None,
                                metadata={'jsonmodel': fields.IntField(validators=validators.Min(18, True))})

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_min_exclusive.json')
    assert compare_schemas(pattern, schema)


def test_max_validator():

    @dataclass
    class Person(DataClassBridge):
        name: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        surname: str | None = field(default=None, metadata={'jsonmodel': fields.StringField()})
        age: int | None = field(default=None, metadata={'jsonmodel': fields.IntField(validators=validators.Max(18))})

    schema = Person.to_json_schema()

    pattern = get_fixture('schema_max.json')
    assert compare_schemas(pattern, schema)
