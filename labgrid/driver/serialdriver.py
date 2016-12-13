import attr
import serial
from ..protocol import ConsoleProtocol
from ..resource import SerialPort
from ..factory import target_factory
from .exception import NoResourceError


@target_factory.reg_driver
@attr.s
class SerialDriver(ConsoleProtocol):
    """
    Driver implementing the ConsoleProtocol interface over a SerialPort connection
    """
    target = attr.ib()

    def __attrs_post_init__(self):
        self.port = self.target.get_resource(SerialPort) #pylint: disable=no-member,attribute-defined-outside-init
        if not self.port:
            raise NoResourceError("Target has no SerialPort Resource")
        self.serial = serial.Serial() #pylint: disable=attribute-defined-outside-init
        self.serial.port = self.port.port
        self.serial.baudrate = self.port.speed
        self.target.drivers.append(self) #pylint: disable=no-member
        self.status = 0 #pylint: disable=attribute-defined-outside-init
        self.serial.timeout = 0
        self.open()


    def read(self, size: int=1, timeout: int=0):
        """
        Reads 'size' bytes from the serialport

        Keyword Arguments:
        size -- amount of bytes to read, defaults to 1024
        """
        self.serial.timeout = 0
        return self.serial.read(size)

    def write(self, data: bytes):
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
