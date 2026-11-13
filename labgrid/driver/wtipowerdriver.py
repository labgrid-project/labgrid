"""Power control for WTI NPS, IPS and NBB Telnet command interfaces."""
import re
import time

import attr

from ..factory import target_factory
from ..protocol import PowerProtocol
from ..step import step
from ..util.proxy import proxymanager
from .common import Driver
from .exception import ExecutionError
from .powerdriver import PowerResetMixin


@target_factory.reg_driver
@attr.s(eq=False)
class WTIPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """Control one outlet on an eight-outlet WTI switch.

    Bind a NetworkPowerPort with model 'wti'. Disable command confirmations
    on the switch. Passwords are optional; authenticated sessions send the
    configured password without exposing it as a step argument.
    """
    bindings = {"port": "NetworkPowerPort"}
    password = attr.ib(default="", repr=False, validator=attr.validators.instance_of(str))
    port_number = attr.ib(default=23, validator=attr.validators.instance_of(int))
    timeout = attr.ib(default=10.0, validator=attr.validators.instance_of(float))
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if not 1 <= int(self.port.index) <= 8:
            raise ValueError("WTI outlet index must be between 1 and 8")
        if self.timeout <= 0 or self.delay < 0:
            raise ValueError("timeout must be positive and delay nonnegative")

    def _expect_prompt(self, connection):
        index, _, response = connection.expect([br'(?:NPS|IPS|NBB)> '], self.timeout)
        if index < 0:
            raise ExecutionError("Timed out waiting for WTI prompt")
        return response

    def _status(self, connection):
        connection.write(b'/S\r\n')
        response = self._expect_prompt(connection)
        # Match a complete outlet number and state, not a substring of a name.
        rows = re.findall(rb'^\s*(\d+)\s*\|[^\r\n]*?\|\s*(ON|OFF)\s*(?:\||$)',
                          response, re.MULTILINE)
        states = [state for index, state in rows if int(index) == int(self.port.index)]
        if len(states) != 1:
            raise ExecutionError(f"No unambiguous WTI status for outlet {self.port.index}")
        return states[0] == b'ON'

    def _request(self, value=None):
        from telnetlib3 import Telnet  # optional dependency
        host, port = proxymanager.get_host_and_port(self.port, force_port=self.port_number)
        try:
            with Telnet(host, port, timeout=self.timeout) as connection:
                if self.password:
                    connection.write(self.password.encode('utf-8') + b'\r\n')
                self._expect_prompt(connection)
                if value is not None:
                    command = 'On' if value else 'Off'
                    connection.write(f'/{command} {int(self.port.index)}\r\n'.encode('ascii'))
                    self._expect_prompt(connection)
                state = self._status(connection)
                if value is not None and state != value:
                    raise ExecutionError("WTI outlet did not reach requested state")
                return state
        except (OSError, EOFError) as exc:
            raise ExecutionError("WTI connection failed") from exc

    @Driver.check_active
    @step()
    def on(self):
        self._request(True)

    @Driver.check_active
    @step()
    def off(self):
        self._request(False)

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self._request()
