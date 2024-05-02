from jsonmodels import models, fields

class Address(models.Base):
    line_1 = fields.StringField()
    line_2 = fields.StringField(nullable=True)
    city = fields.StringField()

class Car(models.Base):
    registration = fields.StringField()

class Boat(models.Base):
    name = fields.StringField()

class Person(models.Base):
    name = fields.StringField()
    surname = fields.StringField()
    age = fields.IntField()
    dob = fields.DateField()
    alive = fields.BoolField()
    last_update = fields.DateTimeField()
    address = fields.EmbeddedField(model_types=Address)
    transport = fields.EmbeddedField(model_types=(Car, Boat))
    pet_names = fields.ListField(items_types=str)
    nicknames = fields.DerivedListField(field=fields.StringField())
    alias_names = fields.DerivedListField(fields.StringField())

class CarRegistry(models.Base):
    registry = fields.MapField(key_field=fields.StringField(), value_field=fields.StringField())
    any_random = fields.GenericField()


person = Person()
address = Address()
car_registry = CarRegistry()
