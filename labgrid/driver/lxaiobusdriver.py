import attr

import requests

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..util.proxy import proxymanager
from .common import Driver
from .exception import ExecutionError
from ..step import step

@target_factory.reg_driver
@attr.s(eq=False)
class LXAIOBusPIODriver(Driver, DigitalOutputProtocol):
    bindings = {
            "pio": {"LXAIOBusPIO", "NetworkLXAIOBusPIO"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def on_activate(self):
        # we can only forward if the backend knows which port to use
        host, port = proxymanager.get_host_and_port(self.pio)
        self._url = 'http://{}:{}/nodes/{}/pins/{}/'.format(
            host, port, self.pio.node, self.pio.pin)

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        if self.pio.invert:
            status = not status
        r = requests.post(
                self._url, data={'value': '1' if status else '0'}
        )
        r.raise_for_status()
        j = r.json()
        if j["code"] != 0:
            raise ExecutionError("failed to set value: {}".format(j["error_message"]))

    @Driver.check_active
    @step(result=['True'])
    def get(self):
        r = requests.get(self._url)
        r.raise_for_status()
        j = r.json()
        if j["code"] != 0:
            raise ExecutionError("failed to get value: {}".format(j["error_message"]))
        result = j["result"]
        if result not in (0, 1):
            raise ExecutionError("invalid input value: {}".format(repr(result)))
        status = bool(result)
        if self.pio.invert:
            status = not status
        return status
