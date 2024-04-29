from models import person

reveal_type(person.nicknames)
# expect: builtins.list[builtins.str]
