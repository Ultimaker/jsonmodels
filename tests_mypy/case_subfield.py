from jsonmodels import models, fields


class SubStringField(fields.StringField):
    pass

class TestModel(models.Base):
    name = SubStringField()

test_instance = TestModel()

reveal_type(test_instance.name)
# expect: builtins.str
