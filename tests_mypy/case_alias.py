from jsonmodels import models, fields

first_name_field = fields.StringField

class AliasModel(models.Base):
    name = first_name_field()

alias = AliasModel()

reveal_type(alias.name)
# expect: builtins.str
