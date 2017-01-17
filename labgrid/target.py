import attr

from .binding import BindingError, BindingState
from .driver import Driver
from .exceptions import NoDriverFoundError, NoResourceFoundError
from .resource import Resource
from .util import Timeout
from .step import step


@attr.s
class Target:
    name = attr.ib(validator=attr.validators.instance_of(str))
    env = attr.ib(default=None)

    def __attrs_post_init__(self):
        self.resources = []
        self.drivers = []

    def interact(self, msg):
        if self.env:
            self.env.interact("{}: {}".format(self.name, msg))
        else:
            input(msg)

    @step()
    def await_resources(self):
        # TODO: store timeout in managed resources and use maximum
        timeout = Timeout(2.0)
        waiting = set(self.resources)
        while waiting and not timeout.expired:
            waiting = set(r for r in waiting if not r.avail)
            for r in waiting:
                r.poll()
            # TODO: sleep if no progress
        if waiting:
            raise NoResourceFoundError("Not all resources are available: {}".format(waiting))

    def get_resource(self, cls):
        """
        Helper function to get a resource of the target.
        Returns the first valid resource found, otherwise None.

        Arguments:
        cls -- resource-class to return as a resource
        """
        for res in self.resources:
            if isinstance(res, cls):
                return res
        raise NoResourceFoundError(
            "no resource matching {} found in target {}".format(cls, self)
        )

    def get_driver(self, cls):
        """
        Helper function to get a driver of the target.
        Returns the first valid driver found, otherwise None.

        Arguments:
        cls -- driver-class to return as a resource
        """
        for drv in self.drivers:
            if isinstance(drv, cls):
                return drv
        raise NoDriverFoundError(
            "no driver matching {} found in target {}".format(cls, self)
        )

    def get_active_driver(self, cls):
        """
        Helper function to get the active driver of the target.
        Returns the active driver found, otherwise None.

        Arguments:
        cls -- driver-class to return as a resource
        """
        for drv in self.drivers:
            if isinstance(drv, cls):
                if drv.state == BindingState.active:
                    return drv
        raise NoDriverFoundError(
            "no driver matching {} found in target {}".format(cls, self)
        )

    def get(self, cls):
        if issubclass(cls, Resource):
            return self.get_resource(cls)
        else:
            return self.get_driver(cls)

    def bind_resource(self, resource):
        """
        Bind the resource to this target.
        """
        if resource.state is not BindingState.idle:
            raise BindingError(
                "{} is not in state {}".format(resource, BindingState.idle)
            )

        # consistency check
        assert isinstance(resource, Resource)
        assert not resource.bindings
        assert resource not in self.resources
        assert resource.target is None

        # update state
        self.resources.append(resource)
        resource.target = self
        resource.state = BindingState.bound

    def bind_driver(self, client):
        """
        Bind the driver to all suppliers (resources and other drivers).

        Currently, we only support binding all suppliers at once.
        """
        if client.state is not BindingState.idle:
            raise BindingError(
                "{} is not in state {}".format(client, BindingState.idle)
            )

        # consistency check
        assert isinstance(client, Driver)
        assert client not in self.drivers
        assert client.target is None

        # locate suppliers
        suppliers = []
        for name, cls in client.bindings.items():
            supplier = self.get(cls)
            setattr(client, name, supplier)
            suppliers.append(supplier)

        # consistency checks
        for supplier in suppliers:
            assert supplier.target is self
            assert client not in supplier.clients
            assert supplier not in client.suppliers

        # update relationship in both directions
        self.drivers.append(client)
        client.target = self
        for supplier in suppliers:
            supplier.clients.add(client)
            client.suppliers.add(supplier)
            client.on_supplier_bound(supplier, name)
            supplier.on_client_bound(client)
        client.state = BindingState.bound

    def bind(self, bindable):
        if isinstance(bindable, Resource):
            return self.bind_resource(bindable)
        elif isinstance(bindable, Driver):
            return self.bind_driver(bindable)
        else:
            raise BindingError("object {} is not bindable".format(bindable))

    def activate(self, client):
        """
        Activate the client by activating all bound suppliers. This may require
        deactivating other clients.
        """
        if client.state is BindingState.active:
            return  # nothing to do

        if client.state is not BindingState.bound:
            raise BindingError(
                "{} is not in state {}".format(client, BindingState.bound)
            )

        # consistency check
        assert client in self.resources or client in self.drivers

        # TODO: wait until resources are available?

        # activate recursively and resolve conflicts
        for supplier in client.suppliers:
            if supplier.state is not BindingState.active:
                self.activate(supplier)
            supplier.resolve_conflicts(client)

        # update state
        client.on_activate()
        client.state = BindingState.active

    def deactivate(self, client):
        """
        Recursively deactivate the client's clients and itself.

        This is needed to ensure that no client has an inactive supplier.
        """
        if client.state is BindingState.bound:
            return  # nothing to do

        if client.state is not BindingState.active:
            raise BindingError(
                "{} is not in state {}".format(client, BindingState.active)
            )

        # consistency check
        assert client in self.resources or client in self.drivers

        # update state
        client.on_deactivate()
        client.state = BindingState.bound

    def cleanup(self):
        """Clean up conntected drivers and resources in reversed order"""
        for drv in reversed(self.drivers):
            if hasattr(drv, 'cleanup') and callable(getattr(drv, 'cleanup')):
                drv.cleanup()
        for res in reversed(self.resources):
            if hasattr(res, 'cleanup') and callable(getattr(res, 'cleanup')):
                res.cleanup()
