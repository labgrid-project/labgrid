import enum
from functools import wraps
from typing import Any, Dict

import attr


@attr.s(eq=False)
class StateError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s(eq=False)
class BindingError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@enum.unique
class BindingState(enum.Enum):
    error = -1
    idle = 0
    bound = 1
    active = 2


@attr.s(eq=False)
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

    bindings: Dict[str, Any] = {}

    # these are controlled by the Target
    target = attr.ib()
    name = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)))
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

    @property
    def display_name(self):
        if self.name:
            return f"{self.__class__.__name__}(target={self.target.name}, name={self.name})"

        return f"{self.__class__.__name__}(target={self.target.name})"

    def on_supplier_bound(self, supplier):
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

    def get_bound_resources(self):
        """
        Called by the Target to find the correct driver corresponding to a resource
        """
        raise NotImplementedError("get_bound_resources not implemented!")

    @classmethod
    def check_active(cls, func):
        @wraps(func)
        def wrapper(self, *_args, **_kwargs):
            if self.state is not BindingState.active:
                raise StateError(
                    f'{self} has not been activated, {func.__qualname__} cannot be called in state "{self.state.name}"'  # pylint: disable=line-too-long
                )
            return func(self, *_args, **_kwargs)

        return wrapper

    @classmethod
    def check_bound(cls, func):
        @wraps(func)
        def wrapper(self, *_args, **_kwargs):
            if self.state is BindingState.active:
                raise StateError(
                    f'{self} is active, but must be deactivated to call {func.__qualname__}'
                )
            elif self.state is not BindingState.bound:
                raise StateError(
                    f'{self} has not been bound, {func.__qualname__} cannot be called in state "{self.state.name}"'  # pylint: disable=line-too-long
                )
            return func(self, *_args, **_kwargs)

        return wrapper

    class NamedBinding:
        """
        Marks a binding (or binding set) as requiring an explicit name.
        """
        def __init__(self, value):
            self.value = value

        def __repr__(self):
            return f"Binding.Named({repr(self.value)})"
