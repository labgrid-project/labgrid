import abc
import logging
from time import monotonic

import attr

from .binding import BindingError, BindingState
from .driver import Driver
from .exceptions import NoSupplierFoundError, NoDriverFoundError, NoResourceFoundError
from .resource import Resource, ManagedResource
from .strategy import Strategy
from .util import Timeout


@attr.s(cmp=False)
class Target:
    name = attr.ib(validator=attr.validators.instance_of(str))
    env = attr.ib(default=None)

    def __attrs_post_init__(self):
        self.log = logging.getLogger("target({})".format(self.name))
        self.resources = []
        self.drivers = []
        self.last_update = 0.0

    def interact(self, msg):
        if self.env:
            self.env.interact("{}: {}".format(self.name, msg))
        else:
            input(msg)

    def update_resources(self):
        """
        Iterate over all relevant managers and deactivate any active but
        unavailable resources.
        """
        if (monotonic() - self.last_update) < 0.1:
            return
        self.last_update = monotonic()
        resources = [r for r in self.resources if isinstance(r, ManagedResource)]
        managers = set(r.manager for r in resources)
        for manager in managers:
            manager.poll()
        for resource in resources:
            if not resource.avail and resource.state is BindingState.active:
                self.log.info("deactivating unavailable resource {}".format(
                    resource.display_name))
                self.deactivate(resource)

    def await_resources(self, resources, timeout=None):
        """
        Poll the given resources and wait until they are available.
        """
        self.update_resources()

        waiting = set(resource for resource in resources if isinstance(resource, ManagedResource))
        if not waiting:
            return
        if timeout is None:
            timeout = Timeout(max(resource.timeout for resource in waiting))
        else:
            timeout = Timeout(timeout)
        while waiting and not timeout.expired:
            waiting = set(r for r in waiting if not r.avail)
            managers = set(r.manager for r in waiting)
            for m in managers:
                m.poll()
            # TODO: sleep if no progress
        if waiting:
            raise NoResourceFoundError(
                "Not all resources are available: {}".format(waiting),
                filter=waiting
            )

    def get_resource(self, cls, *, name=None, await=True):
        """
        Helper function to get a resource of the target.
        Returns the first valid resource found, otherwise None.

        Arguments:
        cls -- resource-class to return as a resource
        name -- optional name to use as a filter
        await -- wait for the resource to become available (default True)
        """
        found = []
        for res in self.resources:
            if not isinstance(res, cls):
                continue
            if name and res.name != name:
                continue
            found.append(res)
        if len(found) == 0:
            raise NoResourceFoundError(
                "no resource matching {} found in target {}".format(cls, self)
            )
        elif len(found) > 1:
            raise NoResourceFoundError(
                "multiple resources matching {} found in target {}".format(cls, self)
            )
        if await:
            self.await_resources(found)
        return found[0]

    def get_driver(self, cls, *, name=None, activate=True):
        """
        Helper function to get a driver of the target.
        Returns the first valid driver found, otherwise None.

        Arguments:
        cls -- driver-class to return as a resource
        name -- optional name to use as a filter
        activate -- activate the driver (default True)
        """
        found = []
        for drv in self.drivers:
            if not isinstance(drv, cls):
                continue
            if name and drv.name != name:
                continue
            found.append(drv)
        if len(found) == 0:
            raise NoDriverFoundError(
                "no driver matching {} found in target {}".format(cls, self)
            )
        elif len(found) > 1:
            raise NoDriverFoundError(
                "multiple drivers matching {} found in target {}".format(cls, self)
            )
        if activate:
            self.activate(found[0])
        return found[0]

    def get_active_driver(self, cls, *, name=None):
        """
        Helper function to get the active driver of the target.
        Returns the active driver found, otherwise None.

        Arguments:
        cls -- driver-class to return as a resource
        name -- optional name to use as a filter
        """
        found = []
        for drv in self.drivers:
            if not isinstance(drv, cls):
                continue
            if name and drv.name != name:
                continue
            if drv.state != BindingState.active:
                continue
            found.append(drv)
        if len(found) == 0:
            raise NoDriverFoundError(
                "no driver matching {} found in target {}".format(cls, self)
            )
        elif len(found) > 1:
            raise NoDriverFoundError(
                "multiple drivers matching {} found in target {}".format(cls, self)
            )
        return found[0]

    def __getitem__(self, key):
        """
        Syntactic sugar to access drivers by class (optionally filtered by
        name).

        >>> target = Target('main')
        >>> console = FakeConsoleDriver(target, 'console')
        >>> target.activate(console)
        >>> target[FakeConsoleDriver]
        FakeConsoleDriver(target=Target(name='main', …), name='console', …)
        >>> target[FakeConsoleDriver, 'console']
        FakeConsoleDriver(target=Target(name='main', …), name='console', …)
        """
        name = None
        if not isinstance(key, tuple):
            cls = key
        elif len(key) == 2:
            cls, name = key
        if not issubclass(cls, (Driver, abc.ABC)): # all Protocols derive from ABC
            raise NoDriverFoundError(
                "invalid driver class {}".format(cls)
            )

        return self.get_active_driver(cls, name=name)

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
        bound_suppliers = []
        for name, requirements in client.bindings.items():
            # use sets even for a single requirement
            if not isinstance(requirements, set):
                requirements = {requirements}
            errors = []
            suppliers = []
            for requirement in requirements:
                try:
                    if issubclass(requirement, Resource):
                        suppliers.append(
                            self.get_resource(requirement, await=False),
                        )
                    else:
                        suppliers.append(
                            self.get_driver(requirement, activate=False),
                        )

                except NoSupplierFoundError as e:
                    errors.append(e)
            if not suppliers:
                if len(errors) == 1:
                    raise errors[0]
                else:
                    raise NoSupplierFoundError(
                        "no supplier matching {} found in target {}".format(requirements, self)
                    )
            elif len(suppliers) > 1:
                raise NoSupplierFoundError(
                    "conflicting suppliers matching {} found in target {}".format(requirements, self)
                )
            setattr(client, name, suppliers[0])
            bound_suppliers.append(suppliers[0])

        # consistency checks
        for supplier in bound_suppliers:
            assert supplier.target is self
            assert client not in supplier.clients
            assert supplier not in client.suppliers

        # update relationship in both directions
        self.drivers.append(client)
        client.target = self
        for supplier in bound_suppliers:
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
        # don't activate strategies, they usually have conflicting bindings
        if isinstance(client, Strategy):
            return

        if client.state is BindingState.active:
            return  # nothing to do

        if client.state is not BindingState.bound:
            raise BindingError(
                "{} is not in state {}".format(client, BindingState.bound)
            )

        # consistency check
        assert client in self.resources or client in self.drivers

        # wait until resources are available
        resources = [resource for resource in client.suppliers if isinstance(resource, Resource)]
        self.await_resources(resources)

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

        for cli in client.clients:
            self.deactivate(cli)

        # update state
        client.on_deactivate()
        client.state = BindingState.bound

    def cleanup(self):
        """Clean up conntected drivers and resources in reversed order"""
        for drv in reversed(self.drivers):
            self.deactivate(drv)
        for res in reversed(self.resources):
            self.deactivate(res)
