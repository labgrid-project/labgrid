import attr

from ..binding import BindingMixin


@attr.s
class Resource(BindingMixin):
    """
    Represents a resource which is used by drivers. It only stores information
    and does not implement any actual functionality.

    Resources can exist without a target, but they must be bound to one before
    use.

    Life cycle:
    - create
    - bind (n times)
    """
