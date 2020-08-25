"""Predefined validators."""
import re

from six.moves import reduce

from .errors import MinValidationError, MaxValidationError, BadTypeError, \
    RegexError, MinLengthError, MaxLengthError, EnumError
from . import utilities


class Validator(object):
    """Base type for all validators, to be used in type hints.

    For example:

    >>> def my_func(validator: Validator):
    >>>     ...
    >>>
    >>> my_func(Min(1))
    >>> my_func(Max(1))
    """


class Min(Validator):

    """Validator for minimum value."""

    def __init__(self, minimum_value, exclusive=False):
        """Init.

        :param minimum_value: Minimum value for validator.
        :param bool exclusive: If `True`, then validated value must be strongly
            lower than given threshold.

        """
        self.minimum_value = minimum_value
        self.exclusive = exclusive

    def validate(self, value):
        """Validate value."""
        if value < self.minimum_value \
                or (self.exclusive and value == self.minimum_value):
            raise MinValidationError(value, self.minimum_value, self.exclusive)

    def modify_schema(self, field_schema):
        """Modify field schema."""
        field_schema['minimum'] = self.minimum_value
        if self.exclusive:
            field_schema['exclusiveMinimum'] = True


class Max(Validator):

    """Validator for maximum value."""

    def __init__(self, maximum_value, exclusive=False):
        """Init.

        :param maximum_value: Maximum value for validator.
        :param bool exclusive: If `True`, then validated value must be strongly
            bigger than given threshold.

        """
        self.maximum_value = maximum_value
        self.exclusive = exclusive

    def validate(self, value):
        """Validate value."""
        if value > self.maximum_value \
                or (self.exclusive and value == self.maximum_value):
            raise MaxValidationError(value, self.maximum_value, self.exclusive)

    def modify_schema(self, field_schema):
        """Modify field schema."""
        field_schema['maximum'] = self.maximum_value
        if self.exclusive:
            field_schema['exclusiveMaximum'] = True


class Regex(Validator):

    """Validator for regular expressions."""

    FLAGS = {
        'ignorecase': re.I,
        'multiline': re.M,
    }

    def __init__(self, pattern, custom_error=None, **flags):
        """Init.

        Note, that if given pattern is ECMA regex, given flags will be
        **completely ignored** and taken from given regex.


        :param string pattern: Pattern of regex.
        :param custom_error: Custom exception raised if the regex fails.
        :param bool flags: Flags used for the regex matching.
            Allowed flag names are in the `FLAGS` attribute. The flag value
            does not matter as long as it evaluates to True.
            Flags with False values will be ignored.
            Invalid flags will be ignored.

        """
        self.custom_error = custom_error
        if utilities.is_ecma_regex(pattern):
            result = utilities.convert_ecma_regex_to_python(pattern)
            self.pattern, self.flags = result
        else:
            self.pattern = pattern
            self.flags = [self.FLAGS[key] for key, value in flags.items()
                          if key in self.FLAGS and value]

    def validate(self, value):
        """Validate value."""
        flags = self._calculate_flags()

        try:
            result = re.search(self.pattern, value, flags)
        except TypeError:
            raise BadTypeError(value, (str,), is_list=False)

        if not result:
            if self.custom_error:
                raise self.custom_error
            raise RegexError(value, self.pattern)

    def _calculate_flags(self):
        return reduce(lambda x, y: x | y, self.flags, 0)

    def modify_schema(self, field_schema):
        """Modify field schema."""
        field_schema['pattern'] = utilities.convert_python_regex_to_ecma(
            self.pattern, self.flags
        )


class Length(Validator):

    """Validator for length."""

    def __init__(self, minimum_value=None, maximum_value=None):
        """Init.

        Note that if no `minimum_value` neither `maximum_value` will be
        specified, `ValueError` will be raised.

        :param int minimum_value: Minimum value (optional).
        :param int maximum_value: Maximum value (optional).

        """
        if minimum_value is None and maximum_value is None:
            raise ValueError(
                "Either 'minimum_value' or 'maximum_value' must be specified."
            )

        self.minimum_value = minimum_value
        self.maximum_value = maximum_value

    def validate(self, value):
        """Validate value."""
        len_ = len(value)

        if self.minimum_value is not None and len_ < self.minimum_value:
            raise MinLengthError(value, self.minimum_value)

        if self.maximum_value is not None and len_ > self.maximum_value:
            raise MaxLengthError(value, self.maximum_value)

    def modify_schema(self, field_schema):
        """Modify field schema."""
        is_array = field_schema.get('type') == 'array'

        if self.minimum_value:
            key = 'minItems' if is_array else 'minLength'
            field_schema[key] = self.minimum_value

        if self.maximum_value:
            key = 'maxItems' if is_array else 'maxLength'
            field_schema[key] = self.maximum_value


class Enum(Validator):

    """Validator for enums."""

    def __init__(self, *choices):
        """Init.

        :param [] choices: Valid choices for the field.
        """

        self.choices = list(choices)

    def validate(self, value):
        if value not in self.choices:
            raise EnumError(value, self.choices)

    def modify_schema(self, field_schema):
        field_schema['enum'] = self.choices
