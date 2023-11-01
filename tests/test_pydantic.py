from collections import OrderedDict
import datetime
from datetime import timezone

import pytest
from jsonmodels import models, fields, validators, errors


def test_bool_field():

    field = fields.BoolField()

    class Person(models.Base):

        is_programmer: bool = field

    person = Person()
    assert person.is_programmer is None

    person.is_programmer = True
    assert person.is_programmer is True

    person.is_programmer = False
    assert person.is_programmer is False

    assert field.parse_value(True) is True
    assert field.parse_value('something') is True
    assert field.parse_value(object()) is True

    assert field.parse_value(None) is None

    assert field.parse_value(False) is False
    assert field.parse_value(0) is False
    assert field.parse_value('') is False
    assert field.parse_value([]) is False
