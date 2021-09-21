import logging
import warnings

import attr
from packaging import version
from pexpect import TIMEOUT
import serial
import serial.rfc2217

from ..factory import target_factory
from ..protocol import ConsoleProtocol
from .common import Driver
from .consoleexpectmixin import ConsoleExpectMixin
from ..util.proxy import proxymanager
from ..resource import SerialPort


@target_factory.reg_driver
@attr.s(eq=False)
class SerialDriver(ConsoleExpectMixin, Driver, ConsoleProtocol):
    """
    Driver implementing the ConsoleProtocol interface over a SerialPort connection
    """
    # pyserial 3.2.1 does not support RFC2217 under Python 3
    # https://github.com/pyserial/pyserial/pull/183
    if version.parse(serial.__version__) <= version.Version('3.2.1'):
        bindings = {"port": "SerialPort", }
    else:
        bindings = {"port": {"SerialPort", "NetworkSerialPort"}, }
    if version.parse(serial.__version__) != version.Version('3.4.0.1'):
        message = ("The installed pyserial version does not contain important RFC2217 fixes.\n"
                   "You can install the labgrid fork via:\n"
                   "pip uninstall pyserial\n"
                   "pip install https://github.com/labgrid-project/pyserial/archive/v3.4.0.1.zip#egg=pyserial\n")  # pylint: disable=line-too-long
        warnings.warn(message)

    txdelay = attr.ib(default=0.0, validator=attr.validators.instance_of(float))
    timeout = attr.ib(default=3.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger(f"{self}({self.target})")
        if isinstance(self.port, SerialPort):
            self.serial = serial.Serial()
        else:
            if self.port.protocol == "rfc2217":
                self.serial = serial.rfc2217.Serial()
            elif self.port.protocol == "raw":
                self.serial = serial.serial_for_url("socket://", do_not_open=True)
            else:
                raise Exception("SerialDriver: unknown protocol")
        self.status = 0

    def on_activate(self):
        if isinstance(self.port, SerialPort):
            self.serial.port = self.port.port
            self.serial.baudrate = self.port.speed
        else:
            host, port = proxymanager.get_host_and_port(self.port)
            if self.port.protocol == "rfc2217":
                self.serial.port = f"rfc2217://{host}:{port}?ign_set_control&timeout={self.timeout}"
            elif self.port.protocol == "raw":
                self.serial.port = f"socket://{host}:{port}/"
            else:
                raise Exception("SerialDriver: unknown protocol")
            self.serial.baudrate = self.port.speed
        self.open()

    def on_deactivate(self):
        self.close()

    def _read(self, size: int = 1, timeout: float = 0.0):
        """
        Reads 'size' or more bytes from the serialport

        Keyword Arguments:
        size -- amount of bytes to read, defaults to 1
        """
        reading = max(size, self.serial.in_waiting)
        self.serial.timeout = timeout
        res = self.serial.read(reading)
        if not res:
            raise TIMEOUT(f"Timeout of {timeout:.2f} seconds exceeded or connection closed by peer")
        return res

    def _write(self, data: bytes):
        """
        Writes 'data' to the serialport

        Arguments:
        data -- data to write, must be bytes
        """
        return self.serial.write(data)

    def open(self):
        """Opens the serialport, does nothing if it is already closed"""
        if not self.status:
            try:
                self.serial.open()
            except serial.SerialException as e:
                raise serial.SerialException(
                    f"Could not open serial port {self.serial.port}: {str(e)}") from e

            self.status = 1

    def close(self):
        """Closes the serialport, does nothing if it is already closed"""
        if self.status:
            self.serial.close()
            self.status = 0
