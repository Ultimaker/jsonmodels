from models import address

reveal_type(address.line_1)
# expect: builtins.str

reveal_type(address.line_2)
# expect: Union[builtins.str, None]
