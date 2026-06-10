"""
This driver implements a digital output driver for the robot electronics 8 relay
outputs board (ETH008).

Driver has been tested with:
* ETH008 - 8 relay outputs
"""

import socket
import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from ..util.proxy import proxymanager
from .common import Driver
from .exception import ExecutionError

PORT = 17494  # TCP port for ETH008 (0x4456)


@target_factory.reg_driver
@attr.s(eq=False)
class Eth008DigitalOutputDriver(Driver, DigitalOutputProtocol):
    """Eth008DigitalOutputDriver - Driver to control individual relays on ETH008 as digital outputs"""
    bindings = {"output": {"Eth008DigitalOutput"}, }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._host = None
        self._port = None

    def on_activate(self):
        self._host, self._port = proxymanager.get_host_and_port(
            self.output, force_port=PORT
        )

    def _send_tcp_command(self, command_bytes):
        """Send a command over TCP and return the response."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect((self._host, self._port))
            s.sendall(command_bytes)
            response = s.recv(1)
            return response

    @Driver.check_active
    @step(args=["status"])
    def set(self, status):
        index = int(self.output.index)
        assert 1 <= index <= 8

        if self.output.invert:
            status = not status

        # Use TCP command: 0x20 for active (on), 0x21 for inactive (off)
        command = 0x20 if status else 0x21
        # Permanent mode (time = 0)
        command_bytes = bytes([command, index, 0])

        response = self._send_tcp_command(command_bytes)

        # Check response: 0 for success, 1 for failure
        if response == b'\x01':
            raise ExecutionError(f"failed to set port {index} to status {status}")
        elif response != b'\x00':
            raise ExecutionError(f"unexpected response from device: {response}")

    @Driver.check_active
    @step(result=["True"])
    def get(self):
        index = int(self.output.index)
        assert 1 <= index <= 8

        # Use TCP command: 0x24 to get all relay states
        # The response is 1 byte where each bit represents a relay state
        command_bytes = bytes([0x24])

        response = self._send_tcp_command(command_bytes)

        # Parse the response byte
        # Each bit represents a relay: bit 0 = relay 1, bit 1 = relay 2, etc.
        state_byte = response[0]
        # Get the bit corresponding to the relay index (1-8)
        relay_bit = (state_byte >> (index - 1)) & 0x01
        state = bool(relay_bit)

        if self.output.invert:
            state = not state

        return state
