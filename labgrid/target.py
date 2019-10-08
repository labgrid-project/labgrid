import abc
import logging
from time import monotonic, sleep
from collections import Counter

import attr

from .binding import BindingError, BindingState
from .driver import Driver
from .exceptions import NoSupplierFoundError, NoDriverFoundError, NoResourceFoundError
from .resource import Resource
from .strategy import Strategy
from .util import Timeout


@attr.s(eq=False)
class Target:
    name = attr.ib(validator=attr.validators.instance_of(str))
    env = attr.ib(default=None)

    def __attrs_post_init__(self):
        self.log = logging.getLogger("target({})".format(self.name))
        self.resources = []
        self.drivers = []
        self.last_update = 0.0
        # This should really be an argument for Drivers, but currently attrs
        # doesn't support keyword only agruments, so we can't add an optional
        # argument at the BindingMixin level.
        # https://github.com/python-attrs/attrs/issues/106
        self._binding_map = {}
        self._lookup_table = {}

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
        resources = [r for r in self.resources if r.get_managed_parent()]
        managers = set(r.get_managed_parent().manager for r in resources)
        for manager in managers:
            manager.poll()
        for resource in resources:
            if not resource.avail and resource.state is BindingState.active:
                self.log.info("deactivating unavailable resource %s", resource.display_name)  # pylint: disable=line-too-long
                self.deactivate(resource)

    def await_resources(self, resources, timeout=None, avail=True):
        """
        Poll the given resources and wait until they are (un-)available.

        Args:
            resources (List): the resources to poll
            timeout (float): optional timeout
            avail (bool): optionally wait until the resources are unavailable with avail=False
        """
        self.update_resources()

        waiting = set(r for r in resources if r.avail != avail)
        static = set(r for r in waiting if r.get_managed_parent() is None)
        if static:
            raise NoResourceFoundError("Static resources are not {}: {}".format(
                "available" if avail else "unavailable", static))

        if not waiting:
            return

        if timeout is None:
            timeout = Timeout(max(resource.get_managed_parent().timeout for resource in waiting))
        else:
            timeout = Timeout(timeout)

        while waiting and not timeout.expired:
            waiting = set(r for r in waiting if r.avail != avail)
            managers = set(r.get_managed_parent().manager for r in waiting)
            for m in managers:
                m.poll()
            if not any(r for r in waiting if r.avail == avail):
                # sleep if no progress
                sleep(0.5)

        if waiting:
            raise NoResourceFoundError(
                "Not all resources are {}: {}".format(
                    "available" if avail else "unavailable", waiting),
                filter=waiting
            )

        self.update_resources()

    def get_resource(self, cls, *, name=None, wait_avail=True):
        """
        Helper function to get a resource of the target.
        Returns the first valid resource found, otherwise a
        NoResourceFoundError is raised.

        Arguments:
        cls -- resource-class to return as a resource
        name -- optional name to use as a filter
        wait_avail -- wait for the resource to become available (default True)
        """
        found = []
        other_names = []
        if isinstance(cls, str):
            cls = self._class_from_string(cls)

        for res in self.resources:
            if not isinstance(res, cls):
                continue
            if name and res.name != name:
                other_names.append(res.name)
                continue
            found.append(res)
        if not found:
            if other_names:
                raise NoResourceFoundError(
                    "all resources matching {} found in target {} have other names: {}".format(
                        cls, self, other_names)
                )
            else:
                raise NoResourceFoundError(
                    "no resource matching {} found in target {}".format(cls, self)
                )
        elif len(found) > 1:
            raise NoResourceFoundError(
                "multiple resources matching {} found in target {}".format(cls, self)
            )
        if wait_avail:
            self.await_resources(found)
        return found[0]

    def _get_driver(self, cls, *, name=None, activate=True, active=False):
        assert not (activate is True and active is True)

        found = []
        other_names = []
        if isinstance(cls, str):
            cls = self._class_from_string(cls)

        for drv in self.drivers:
            if not isinstance(drv, cls):
                continue
            if name and drv.name != name:
                other_names.append(drv.name)
                continue
            if active and drv.state != BindingState.active:
                continue
            found.append(drv)
        if not found:
            if other_names:
                raise NoDriverFoundError(
                    "all {}drivers matching {} found in target {} have other names: {}".format(
                        "active " if active else "",
                        cls, self, other_names)
                )
            else:
                raise NoDriverFoundError(
                    "no {}driver matching {} found in target {}".format(
                        "active " if active else "", cls, self
                    )
                )
        elif len(found) > 1:
            prio_last = -255
            prio_found = []
            for drv in found:
                prio = drv.get_priority(cls)
                if prio > prio_last:
                    prio_found = []
                    prio_found.append(drv)
                    prio_last = prio
                elif prio == prio_last:
                    prio_found.append(drv)

            if len(prio_found) == 1:
                found = prio_found
            else:
                raise NoDriverFoundError(
                    "multiple {}drivers matching {} found in target {} with the same priorities".
                    format("active " if active else "", cls, self)
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
        return self._get_driver(cls, name=name, activate=False, active=True)

    def get_driver(self, cls, *, name=None, activate=True):
        """
        Helper function to get a driver of the target.
        Returns the first valid driver found, otherwise None.

        Arguments:
        cls -- driver-class to return as a resource
        name -- optional name to use as a filter
        activate -- activate the driver (default True)
        """
        return self._get_driver(cls, name=name, activate=activate)

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
        if isinstance(cls, str):
            cls = self._class_from_string(cls)
        if not issubclass(cls, (Driver, abc.ABC)): # all Protocols derive from ABC
            raise NoDriverFoundError(
                "invalid driver class {}".format(cls)
            )

        return self.get_active_driver(cls, name=name)

    def set_binding_map(self, mapping):
        """
        Configure the binding name mapping for the next driver only.
        """
        self._binding_map = mapping

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
        # update lookup table
        self._lookup_table[resource.__class__.__name__] = resource.__class__
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

        mapping = self._binding_map
        self._binding_map = {}

        # locate suppliers
        bound_suppliers = []
        for name, requirements in client.bindings.items():
            explicit = False
            if isinstance(requirements, Driver.NamedBinding):
                requirements = requirements.value
                explicit = True
            supplier_name = mapping.get(name)
            if explicit and supplier_name is None:
                raise BindingError(
                    "supplier for {} ({}) of {} in target {} requires an explicit name".format(
                        name, requirements, client, self)
                )
            # use sets even for a single requirement and make a local copy
            if not isinstance(requirements, set):
                requirements = {requirements}
            else:
                requirements = requirements.copy()
            # None indicates that the binding is optional
            optional = None in requirements
            requirements.discard(None)

            errors = []
            suppliers = []
            for requirement in requirements:
                # convert class name string to classes
                if isinstance(requirement, str):
                    requirement = self._class_from_string(requirement)
                try:
                    if issubclass(requirement, Resource):
                        suppliers.append(
                            self.get_resource(requirement, name=supplier_name, wait_avail=False),
                        )
                    elif issubclass(requirement, (Driver, abc.ABC)): # all Protocols derive from ABC
                        suppliers.append(
                            self.get_driver(requirement, name=supplier_name, activate=False),
                        )
                    else:
                        raise NoSupplierFoundError("invalid binding type {}".format(requirement))
                except NoSupplierFoundError as e:
                    errors.append(e)
            if not suppliers:
                if optional:
                    supplier = None
                elif len(errors) == 1:
                    raise errors[0]
                else:
                    raise NoSupplierFoundError(
                        "no supplier matching {} found in target {} (errors: {})".format(
                            requirements, self, errors)
                    )
            elif len(suppliers) > 1:
                raise NoSupplierFoundError("conflicting suppliers matching {} found in target {}".format(requirements, self))  # pylint: disable=line-too-long
            else:
                supplier = suppliers[0]
            setattr(client, name, supplier)
            if supplier is not None:
                bound_suppliers.append(supplier)

        # consistency checks
        for supplier in bound_suppliers:
            assert supplier.target is self
            assert client not in supplier.clients
            assert supplier not in client.suppliers

        duplicates = {k for k, c in Counter(bound_suppliers).items() if c > 1}
        if duplicates:
            raise BindingError(
                "duplicate bindings {} found in target {}".format(duplicates, self)
            )

        # update relationship in both directions
        self.drivers.append(client)
        # update lookup table
        cls = client.__class__
        self._lookup_table[cls.__name__] = cls
        for c in cls.mro():
            if abc.ABC in c.mro():
                self._lookup_table[c.__name__] = c

        client.target = self
        for supplier in bound_suppliers:
            supplier.clients.add(client)
            client.suppliers.add(supplier)
            client.on_supplier_bound(supplier)
            supplier.on_client_bound(client)
        client.state = BindingState.bound

    def bind(self, bindable):
        if isinstance(bindable, Resource):
            return self.bind_resource(bindable)
        if isinstance(bindable, Driver):
            return self.bind_driver(bindable)

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
        if isinstance(client, str):
            client = self._class_from_string(client)

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

    def deactivate_all_drivers(self):
        """Deactivates all drivers in reversed order they were activated"""
        for drv in reversed(self.drivers):
            self.deactivate(drv)

    def cleanup(self):
        """Clean up conntected drivers and resources in reversed order"""
        self.deactivate_all_drivers()
        for res in reversed(self.resources):
            self.deactivate(res)

    def _class_from_string(self, string: str):
        try:
            return self._lookup_table[string]
        except KeyError:
            raise KeyError("No driver/resource/protocol of type '{}' in lookup table, perhaps not bound?".format(string))
