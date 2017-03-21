import enum
from functools import wraps

import attr


@attr.s
class StateError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class BindingError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@enum.unique
class BindingState(enum.Enum):
    error = -1
    idle = 0
    bound = 1
    active = 2


@attr.s
class BindingMixin:
    """
    Handles the binding and activation of drivers and their supplying resources
    and drivers.

    One client can be bound to many suppliers, and one supplier can be bound by
    many clients.

    Conflicting access to one supplier can be avoided by deactivating
    conflicting clients before activation (using the resolve_conflicts
    callback).
    """

    bindings = {}

    # these are controlled by the Target
    target = attr.ib()
    state = attr.ib(default=BindingState.idle, init=False)

    def __attrs_post_init__(self):
        self.suppliers = set()
        self.clients = set()
        target = self.target
        if target is not None:
            # bind will set it again if successful
            self.target = None
            target.bind(self)
            assert self.target is not None

    def on_supplier_bound(self, supplier, name):
        """Called by the Target after a new supplier has been bound"""
        pass

    def on_client_bound(self, client):
        """Called by the Target after a new client has been bound"""
        pass

    def on_activate(self):
        """Called by the Target when this object has been activated"""
        pass

    def on_deactivate(self):
        """Called by the Target when this object has been deactivated"""
        pass

    def resolve_conflicts(self, client):
        """
        Called by the Target to allow this object to deactivate conflicting
        clients.
        """
        pass

    @classmethod
    def check_active(cls, func):
        @wraps(func)
        def wrapper(self, *_args, **_kwargs):
            if self.state is not BindingState.active:
                raise StateError(
                    "{} can not be called ({} is in state {})".format(
                        func.__qualname__, self, self.state.name)
                )
            return func(self, *_args, **_kwargs)

        return wrapper
