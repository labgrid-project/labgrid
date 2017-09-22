import logging

import attr
import serial
import serial.rfc2217
from pexpect import TIMEOUT

from ..factory import target_factory
from ..protocol import ConsoleProtocol
from ..resource import SerialPort, NetworkSerialPort
from .common import Driver
from .consoleexpectmixin import ConsoleExpectMixin


@target_factory.reg_driver
@attr.s(cmp=False)
class SerialDriver(ConsoleExpectMixin, Driver, ConsoleProtocol):
    """
    Driver implementing the ConsoleProtocol interface over a SerialPort connection
    """
    # pyserial 3.2.1 does not support RFC2217 under Python 3
    # https://github.com/pyserial/pyserial/pull/183
    if tuple(int(x) for x in serial.__version__.split('.')) <= (3, 2, 1):
        bindings = {"port": SerialPort, }
    else:
        bindings = {"port": {SerialPort, NetworkSerialPort}, }

    txdelay = attr.ib(default=0.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}({})".format(self, self.target))
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
            if self.port.protocol == "rfc2217":
                self.serial.port = "rfc2217://{}:{}/".format(self.port.host, self.port.port)
            elif self.port.protocol == "raw":
                self.serial.port = "socket://{}:{}/".format(self.port.host, self.port.port)
            else:
                raise Exception("SerialDriver: unknown protocol")
            self.serial.baudrate = self.port.speed
        self.open()

    def on_deactivate(self):
        self.close()

    def _read(self, size: int=1, timeout: float=0.0):
        """
        Reads 'size' or more bytes from the serialport

        Keyword Arguments:
        size -- amount of bytes to read, defaults to 1
        """
        reading = max(size, self.serial.in_waiting)
        self.serial.timeout = timeout
        res = self.serial.read(reading)
        if not res:
            raise TIMEOUT("Timeout of %.2f seconds exceeded" % timeout)
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
            self.serial.open()
            self.status = 1

    def close(self):
        """Closes the serialport, does nothing if it is already closed"""
        if self.status:
            self.serial.close()
            self.status = 0
