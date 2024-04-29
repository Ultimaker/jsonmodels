from models import person

reveal_type(person.dob)
# expect: datetime.date
