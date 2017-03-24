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

    @property
    def command_prefix(self):
        return []


@attr.s
class NetworkResource(Resource):
    """
    Represents a remote Resource available on another computer.

    This stores a command_prefix to describe how to connect to the remote
    computer.

    Args:
        host (str): remote host the resource is available on
    """
    host = attr.ib(validator=attr.validators.instance_of(str))

    @property
    def command_prefix(self):
        return ['ssh', '-x',
                '-o', 'ConnectTimeout=5',
                '-o', 'PasswordAuthentication=no',
                self.host, '--']


@attr.s
class ResourceManager:
    instances = {}

    @classmethod
    def get(cls):
        instance = ResourceManager.instances.get(cls)
        if instance is None:
            instance = cls()
            ResourceManager.instances[cls] = instance
        return instance

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

    timeout = attr.ib(default=2.0, init=False, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.avail = False
        self.manager = self.manager_cls.get()
        self.manager._add_resource(self)

    def poll(self):
        self.manager.poll()
