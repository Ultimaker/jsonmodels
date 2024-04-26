from typing import Any, Iterable
from .types import CollectionField
from typing_extensions import override

class ModelCollection(list):

    """`ModelCollection` is list which validates stored values.

    Validation is made with use of field passed to `__init__` at each point,
    when new value is assigned.

    """

    def __init__(self, field: CollectionField) -> None:
        super(ModelCollection, self).__init__()
        self.field = field

    @override
    def append(self, value: Any) -> None:
        self.field.validate_single_value(value)
        super(ModelCollection, self).append(value)

    @override
    def __setitem__(self, index: Any, value: Any, /) -> None:
        self.field.validate_single_value(value)
        super(ModelCollection, self).__setitem__(index, value)
