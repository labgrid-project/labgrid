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


@attr.s
class ResourceManager:
    instance = None
    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

@attr.s
class ManagedResource(Resource):
    manager_cls = ResourceManager

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.manager = self.manager_cls()
