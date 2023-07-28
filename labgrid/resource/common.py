import logging
import shlex
from typing import Dict, Type, List
import attr

from ..binding import BindingMixin
from ..util.ssh import sshmanager


@attr.s(eq=False)
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

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._parent = None

        logger_name = self.__class__.__name__
        if self.target:
            logger_name += f"({self.target.name})"
        if self.name:
            logger_name += f":{self.name}"
        self.logger = logging.getLogger(logger_name)

    @property
    def command_prefix(self):
        return []

    def wrap_command(self, command):
        """
        Returns the command as-is, no need for command wrapping for local resources.

        Must stay compatible with NetworkResource.wrap_command().
        """
        return command

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        assert self._parent is None
        self._parent = value

    def get_managed_parent(self):
        """
        For Resources which have been created at runtime, return the
        ManagedResource resource which created it.

        Returns None otherwise.
        """
        return self._parent.get_managed_parent() if self._parent else None

    def poll(self):
        managed_parent = self.get_managed_parent()
        if managed_parent:
            managed_parent.poll()

    def get_bound_resources(self):
        """
        Resources only return themselves in a set, drivers will combine those sets.
        """
        return {self}


@attr.s(eq=False)
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
        host = self.host

        if hasattr(self, 'extra'):
            if self.extra.get('proxy_required'):
                host = self.extra.get('proxy')

        conn = sshmanager.get(host)
        prefix = conn.get_prefix()

        return prefix + ['--']

    def wrap_command(self, command):
        """
        Returns shell-escaped command with prepended command_prefix.

        Must stay compatible with Resource.wrap_command().
        """
        shargs = [shlex.quote(a) for a in command]
        return self.command_prefix + shargs


@attr.s(eq=False)
class ResourceManager:
    instances: 'Dict[Type[ResourceManager], ResourceManager]' = {}

    @classmethod
    def get(cls) -> 'ResourceManager':
        instance = ResourceManager.instances.get(cls)
        if instance is None:
            instance = cls()
            ResourceManager.instances[cls] = instance
        return instance

    def __attrs_post_init__(self):
        self.resources: List[ManagedResource] = []
        self.logger = logging.getLogger(str(self))

    def _add_resource(self, resource: 'ManagedResource'):
        self.resources.append(resource)
        self.on_resource_added(resource)

    def on_resource_added(self, resource: 'ManagedResource'):
        pass

    def poll(self):
        pass


@attr.s(eq=False)
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

    def get_managed_parent(self):
        return self
