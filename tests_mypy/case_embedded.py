from models import person

reveal_type(person.address)
# expect: models.Address

reveal_type(person.transport)
# expect: Union[models.Car, models.Boat]
