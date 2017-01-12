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
    avail = attr.ib(default=True, init=False, validator=attr.validators.instance_of(bool))


@attr.s
class ResourceManager:
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __attrs_post_init__(self):
        self.resources = []

    def _add_resource(self, resource):
        self.resources.append(resource)
        self.on_resource_added(resource)

    def on_resource_added(self, resource):
        pass

    def poll(self):
        pass


@attr.s
class ManagedResource(Resource):
    """
    Represents a resource which can appear and disappear at runtime. Every
    ManagedResource has a corresponding ResourceManager which handles these
    events.
    """
    manager_cls = ResourceManager

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.avail = False
        self.manager = self.manager_cls()
        self.manager._add_resource(self)

    def poll(self):
        self.manager.poll()
