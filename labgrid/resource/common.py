import attr


@attr.s
class Resource():
    """
    Represents a resource which is used by drivers. It only stores information
    and does not implement any actual functionality.

    Life cycle:
    - create
    - bind (n times)
    """
