from time import monotonic
from importlib import import_module

import attr

from ..factory import target_factory
from .common import ManagedResource, ResourceManager


@attr.s(eq=False)
class LXAIOBusNodeManager(ResourceManager):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._requests = import_module('requests')

        self._last = 0.0

    def _get_nodes(self, host):
        try:
            r = self._requests.get(f'http://{host}/nodes/')
            r.raise_for_status()
            j = r.json()
            return j["result"]
        except self._requests.exceptions.ConnectionError:
            self.logger.exception("failed to connect to host %s", host)
            return []

    def poll(self):
        if monotonic()-self._last < 2:
            return  # ratelimit requests
        self._last = monotonic()
        hosts = {r.host for r in self.resources}
        nodes = {h: self._get_nodes(h) for h in hosts}
        for resource in self.resources:
            resource.avail = resource.node in nodes[resource.host]


@attr.s(eq=False)
class LXAIOBusNode(ManagedResource):
    """This resource describes a generic LXA IO BUs Node.

    Args:
        host (str): hostname of the owserver e.g. localhost:4304
        node (str): node name e.g. EthMux-5c12ca8b"""
    manager_cls = LXAIOBusNodeManager

    host = attr.ib(validator=attr.validators.instance_of(str))
    node = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.timeout = 30.0
        super().__attrs_post_init__()


@target_factory.reg_resource
@attr.s(eq=False)
class LXAIOBusPIO(LXAIOBusNode):
    """This resource describes a LXA IO Bus PIO Port.

    Args:
        pin (str): pin label e.g. OUT0
        invert (bool): optional, whether the logic level is inverted (active-low)"""
    pin = attr.ib(validator=attr.validators.instance_of(str))
    invert = attr.ib(default=False, validator=attr.validators.instance_of(bool))
