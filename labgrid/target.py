import abc
import atexit
import logging
import sys
from time import monotonic, sleep

import attr

from .binding import BindingError, BindingState
from .driver import Driver
from .exceptions import NoSupplierFoundError, NoDriverFoundError, NoResourceFoundError, NoStrategyFoundError
from .resource import Resource
from .strategy import Strategy
from .util import Timeout
from .factory import target_factory


@attr.s(eq=False)
class Target:
    name = attr.ib(validator=attr.validators.instance_of(str))
    env = attr.ib(default=None)

    def __attrs_post_init__(self):
        self.log = logging.getLogger(f"target({self.name})")
        self.resources = []
        self.drivers = []
        self.last_update = 0.0
        # This should really be an argument for Drivers, but currently attrs
        # doesn't support keyword only agruments, so we can't add an optional
        # argument at the BindingMixin level.
        # https://github.com/python-attrs/attrs/issues/106
        self._binding_map = {}
        self._lookup_table = {
            Strategy.__name__: Strategy,
        }
        atexit.register(self._atexit_cleanup)

    def interact(self, msg):
        if self.env:
            self.env.interact(f"{self.name}: {msg}")
        else:
            input(msg)

    def update_resources(self):
        """
        Iterate over this target's resources, deactivate any active but
        unavailable resources and also deactivate any drivers using them.
        This ensures a consistent binding states for this target.
        """
        if (monotonic() - self.last_update) < 0.1:
            return
        self.last_update = monotonic()
        for resource in self.resources:
            resource.poll()
            if not resource.avail and resource.state is BindingState.active:
                deactivated = self.deactivate(resource)
                deactivated.remove(resource)
                if deactivated:
                    self.log.info("deactivating unavailable resource %s used by %s",
                        resource.display_name,
                        ", ".join(d.display_name for d in deactivated)
                    )
                else:
                    self.log.debug("deactivating unavailable resource %s (unused)", resource.display_name)  # pylint: disable=line-too-long

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
            raise NoResourceFoundError(
                f"Static resources are not {'available' if avail else 'unavailable'}: {static}"
            )

        if not waiting:
            return

        if timeout is None:
            timeout = Timeout(max(resource.get_managed_parent().timeout for resource in waiting))
        else:
            timeout = Timeout(timeout)

        while waiting and not timeout.expired:
            waiting = set(r for r in waiting if r.avail != avail)
            for r in waiting:
                r.poll()
            if not any(r for r in waiting if r.avail == avail):
                # sleep if no progress
                sleep(0.5)

        if waiting:
            raise NoResourceFoundError(
                f"Not all resources are {'available' if avail else 'unavailable'}: {waiting}",
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
        default = None
        if isinstance(cls, str):
            cls = target_factory.class_from_string(cls)

        for res in self.resources:
            if not isinstance(res, cls):
                continue
            if res.name == "default":
                default = res
            if name and res.name != name:
                other_names.append(res.name)
                continue
            found.append(res)

        # if no explicit resource name is requested and a "default" resource was saved and
        # multiple resources were found, use the default resource
        if not name and default and len(found) != 1:
            found = [default]

        if not found:
            name_msg = f" named '{name}'" if name else ""
            if other_names:
                raise NoResourceFoundError(
                    f"no {cls.__name__} resource{name_msg} found in {self}, matching resources with other names: {other_names}"  # pylint: disable=line-too-long
                )

            raise NoResourceFoundError(
                f"no {cls.__name__} resource{name_msg} found in {self}"
            )
        elif len(found) > 1:
            raise NoResourceFoundError(
                f"multiple resources matching {cls.__name__} found in {self}", found=found
            )
        if wait_avail:
            self.await_resources(found)
        return found[0]

    def _get_driver(self, cls, *, name=None, resource=None, activate=True, active=False):
        assert not (activate is True and active is True)

        found = []
        other_names = []
        if isinstance(cls, str):
            cls = target_factory.class_from_string(cls)

        for drv in self.drivers:
            if not isinstance(drv, cls):
                continue
            if resource and resource not in drv.get_bound_resources():
                continue
            if name and drv.name != name:
                other_names.append(drv.name)
                continue
            if active and drv.state != BindingState.active:
                continue
            found.append(drv)
        if not found:
            name_msg = f" named '{name}'" if name else ""
            if other_names:
                raise NoDriverFoundError(
                    "no {active}{cls} driver{name} found in {target}, matching resources with other names: {other_names}".format(  # pylint: disable=line-too-long
                        active="active " if active else "", cls=cls.__name__, name=name_msg,
                        target=self, other_names=other_names)
                )

            raise NoDriverFoundError(
                f"no {'active ' if active else ''}{cls.__name__} driver{name_msg} found in {self}"
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
                    "multiple {active}drivers matching {cls} found in {target} with the same priorities".format(  # pylint: disable=line-too-long
                        active="active " if active else "", cls=cls.__name__, target=self)
                )
        if activate:
            self.activate(found[0])
        return found[0]

    def get_active_driver(self, cls, *, name=None, resource=None):
        """
        Helper function to get the active driver of the target.
        Returns the active driver found, otherwise None.

        Arguments:
        cls -- driver-class to return as a resource
        name -- optional name to use as a filter
        resource -- optional resource to use as a filter
        """
        return self._get_driver(cls, name=name, resource=resource, activate=False, active=True)

    def get_driver(self, cls, *, name=None, resource=None, activate=True):
        """
        Helper function to get a driver of the target.
        Returns the first valid driver found, otherwise None.

        Arguments:
        cls -- driver-class to return as a resource
        name -- optional name to use as a filter
        resource -- optional resource to use as a filter
        activate -- activate the driver (default True)
        """
        return self._get_driver(cls, name=name, resource=resource, activate=activate)

    def get_strategy(self):
        """
        Helper function to get the strategy of the target.

        Returns the Strategy, if exactly one exists and raises a
        NoStrategyFoundError otherwise.
        """
        found = []
        for drv in self.drivers:
            if not isinstance(drv, Strategy):
                continue
            found.append(drv)
        if not found:
            raise NoStrategyFoundError(f"no Strategy found in {self}")
        elif len(found) > 1:
            raise NoStrategyFoundError(f"multiple Strategies found in {self}")
        return found[0]

    def __getitem__(self, key):
        """
        Syntactic sugar to access drivers by class (optionally filtered by
        name).

        >>> from labgrid import Target
        >>> from labgrid.driver.fake import FakeConsoleDriver
        >>>
        >>> target = Target('main')
        >>> console = FakeConsoleDriver(target, 'console')
        >>> target.activate(console)
        >>> target[FakeConsoleDriver]
        FakeConsoleDriver(target=Target(name='main', env=None), name='console', state=<BindingState.active: 2>, txdelay=0.0)
        >>> target[FakeConsoleDriver, 'console']
        FakeConsoleDriver(target=Target(name='main', env=None), name='console', state=<BindingState.active: 2>, txdelay=0.0)
        """
        name = None
        if not isinstance(key, tuple):
            cls = key
        elif len(key) == 2:
            cls, name = key
        if isinstance(cls, str):
            cls = target_factory.class_from_string(cls)
        if not issubclass(cls, (Driver, abc.ABC)): # all Protocols derive from ABC
            raise NoDriverFoundError(
                f"invalid driver class {cls.__name__}"
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
                f"{resource} is not in state {BindingState.idle}"
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
                f"{client} is not in state {BindingState.idle}"
            )

        # consistency check
        assert isinstance(client, Driver)
        assert client not in self.drivers
        assert client.target is None

        mapping = self._binding_map
        self._binding_map = {}

        # locate suppliers
        bound_suppliers = []
        bound_req_pairs = set()
        for name, requirements in client.bindings.items():
            explicit = False
            if isinstance(requirements, Driver.NamedBinding):
                requirements = requirements.value
                explicit = True
            supplier_name = mapping.pop(name, None)
            if explicit and supplier_name is None:
                raise BindingError(
                    f"supplier for {name} ({requirements}) of {client} in {self} requires an explicit name"  # pylint: disable=line-too-long
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
                    requirement = target_factory.class_from_string(requirement)
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
                        raise NoSupplierFoundError(f"invalid binding type {requirement}")
                except NoSupplierFoundError as e:
                    errors.append(e)
            if not suppliers:
                client_name = client.name or client.__class__.__name__
                if optional:
                    supplier = None
                elif len(errors) == 1:
                    err = errors[0]
                    err_cls = type(err)
                    raise err_cls(f"binding {client_name} failed: {err}") from err
                else:
                    raise NoSupplierFoundError(
                        f"binding {client_name} failed: no supplier matching {requirements} found in {self} (errors: {errors})"
                    )
            elif len(suppliers) > 1:
                raise NoSupplierFoundError(f"conflicting suppliers matching {requirements} found in target {self}")  # pylint: disable=line-too-long
            else:
                supplier = suppliers[0]
            if supplier is not None and (requirement, supplier) in bound_req_pairs:
                raise BindingError(
                    f"duplicate bindings of {supplier} to {name} for {requirement} found in target {self}"  # pylint: disable=line-too-long
                )
            bound_req_pairs.add((requirement, supplier))
            setattr(client, name, supplier)
            if supplier is not None:
                bound_suppliers.append(supplier)

        # consistency checks
        for supplier in bound_suppliers:
            assert supplier.target is self
            assert client not in supplier.clients
            assert supplier not in client.suppliers

        # make sure drivers consume all given bindings
        if mapping and not isinstance(client, Strategy):
            raise BindingError(
                f"{client} got unexpected bindings: {list(mapping.keys())}"
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

        raise BindingError(f"object {bindable} is not bindable")

    def activate(self, client, name=None):
        """
        Activate the client by activating all bound suppliers. This may require
        deactivating other clients.
        """
        # don't activate strategies, they usually have conflicting bindings
        if isinstance(client, Strategy):
            return

        if isinstance(client, str):
            cls = target_factory.class_from_string(client)
            client = self._get_driver(cls, name=name, activate=False, active=False)

        assert client is not None

        if client.state is BindingState.active:
            return  # nothing to do

        if client.state is not BindingState.bound:
            raise BindingError(
                f"{client} is not in state {BindingState.bound}"
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

    def deactivate(self, client, name=None):
        """
        Recursively deactivate the client's clients and itself.

        This is needed to ensure that no client has an inactive supplier.

        Returns the list of all objects that were deactivated
        """
        if isinstance(client, str):
            cls = target_factory.class_from_string(client)
            client = self._get_driver(cls, name=name, activate=False, active=True)

        assert client is not None

        if client.state is BindingState.bound:
            return [] # nothing to do

        if client.state is not BindingState.active:
            raise BindingError(
                f"{client} is not in state {BindingState.active}"
            )

        # consistency check
        assert client in self.resources or client in self.drivers

        deactivated = [client]

        for cli in client.clients:
            deactivated.extend(self.deactivate(cli))

        # update state
        client.on_deactivate()
        client.state = BindingState.bound
        return deactivated

    def deactivate_all_drivers(self):
        """Deactivates all drivers in reversed order they were activated"""
        for drv in reversed(self.drivers):
            self.deactivate(drv)

    def _atexit_cleanup(self):
        try:
            self.cleanup()
        except Exception as e:
            print("An exception occured during cleanup, call the cleanup() "
                  "method on targets yourself to handle exceptions explictly.", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

    def export(self):
        """
        Export information from drivers.

        All drivers are deactivated before being exported, unless their
        skip_deactivate_on_export property is true.

        The Strategy can decide for which driver the export method is called and
        with which name. Otherwise, all drivers are exported.
        """
        try:
            name_map = self.get_strategy().prepare_export()
            selection = set(name_map.keys())
        except NoStrategyFoundError:
            name_map = {}
            selection = set(driver for driver in self.drivers if not isinstance(driver, Strategy))

        assert len(name_map) == len(set(name_map.values())), "duplicate export name"

        # drivers may need to be deactivated for export to avoid conflicts
        for drv in reversed(self.drivers):
            if not drv.skip_deactivate_on_export:
                self.deactivate(drv)

        export_vars = {}
        for driver in selection:
            name = name_map.get(driver)
            if not name:
                name = driver.get_export_name()
            for k, v in driver.get_export_vars().items():
                assert isinstance(k, str), f"key {k} from {driver} is not a string"
                assert isinstance(v, str), f"value {v} for key {k} from {driver} is not a string"
                export_vars[f"LG__{name}_{k}".upper()] = v
        return export_vars


    def cleanup(self):
        """Clean up connected drivers and resources in reversed order"""
        self.deactivate_all_drivers()
        for res in reversed(self.resources):
            self.deactivate(res)
