from models import person

reveal_type(person.pet_names)
# expect: builtins.list[builtins.str]
