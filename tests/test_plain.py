from unittest import mock

from jsonmodels import fields


@mock.patch('jsonmodels.fields.BaseField.to_struct')
def test_toBsonEncodable_calls_to_struct(f):
    """Test if default implementation of toBsonEncodable calls to_struct."""
    field = fields.StringField()
    field.toBsonEncodable(value="text")
    f.assert_called_once()
