from models import person

reveal_type(person.nicknames)
# expect: builtins.list[builtins.str]

reveal_type(person.alias_names)
# expect: builtins.list[builtins.str]
