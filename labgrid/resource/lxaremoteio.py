import logging
import os
import warnings
from collections import OrderedDict
from time import monotonic

import attr
import requests

from ..factory import target_factory
from .common import ManagedResource, ResourceManager
from ..util import Timeout


@attr.s(eq=False)
class LXARemoteIOManager(ResourceManager):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        self.log = logging.getLogger('LXARemoteIOManager')

        self._last = 0.0

    def _get_nodes(self, host):
        try:
            r = requests.get('http://{}/nodes/'.format(host))
            r.raise_for_status()
            j = r.json()
            return j["result"]
        except requests.exceptions.ConnectionError:
            log.exception("failed to connect to host %s", host)
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
class LXARemoteIO(ManagedResource):
    """This resource describes a generic LXA Remote IO Port.

    Args:
        host (str): hostname of the owserver e.g. localhost:4304
        node (str): node name e.g. EthMux-5c12ca8b"""
    manager_cls = LXARemoteIOManager

    host = attr.ib(validator=attr.validators.instance_of(str))
    node = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.timeout = 30.0
        super().__attrs_post_init__()


@target_factory.reg_resource
@attr.s(eq=False)
class LXARemotePIO(LXARemoteIO):
    """This resource describes a Onewire PIO Port.

    Args:
        pin (str): pin label e.g. OUT0
        invert (bool): optional, whether the logic level is inverted (active-low)"""
    pin = attr.ib(validator=attr.validators.instance_of(str))
    invert = attr.ib(default=False, validator=attr.validators.instance_of(bool))
