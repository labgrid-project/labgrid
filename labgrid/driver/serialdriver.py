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
@attr.s
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

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if isinstance(self.port, SerialPort):
            self.serial = serial.Serial()
        else:
            self.serial = serial.rfc2217.Serial()
        self.status = 0
        self.logger = logging.getLogger("{}({})".format(self, self.target))

    def on_activate(self):
        if isinstance(self.port, SerialPort):
            self.serial.port = self.port.port
            self.serial.baudrate = self.port.speed
        else:
            self.serial.port = "rfc2217://{}:{}/".format(self.port.host, self.port.port)
            self.serial.baudrate = self.port.speed
        self.open()

    def _read(self, size: int=1, timeout: int=0):
        """
        Reads 'size' or more bytes from the serialport

        Keyword Arguments:
        size -- amount of bytes to read, defaults to 1
        """
        reading = max(size, self.serial.in_waiting)
        self.serial.timeout = timeout
        res = self.serial.read(reading)
        if res:
            self.logger.debug("Read %i bytes: %s, timeout %.2f, requested size %i",
                              len(res), res, timeout, size)
        else:
            raise TIMEOUT("Timeout of %.2f seconds exceeded" % timeout)
        return res

    def _write(self, data: bytes):
        """
        Writes 'data' to the serialport

        Arguments:
        data -- data to write, must be bytes
        """
        self.logger.debug("Write %i bytes: %s", len(data), data)
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
