from models import car_registry

reveal_type(car_registry.registry)
# expect: builtins.dict[builtins.str, builtins.str]
