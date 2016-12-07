import serial
import attr
from .resource import IOResource

@attr.s
class SerialPort(IOResource):
    target = attr.ib()
    port = attr.ib(validator=attr.validators.instance_of(str))
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))

    def __attrs_post_init__(self):
        self.serial = serial.Serial() #pylint: disable=attribute-defined-outside-init
        self.serial.port = self.port
        self.serial.baudrate = self.speed
        self.serial.timeout = 0
        self.target.resources.append(self) #pylint: disable=no-member
        self.status = 0 #pylint: disable=attribute-defined-outside-init

    def read(self, size: int=1024):
        """
        Reads 'size' bytes from the serialport

        Keyword Arguments:
        size -- amount of bytes to read, defaults to 1024
        """
        return self.serial.read(size)

    def write(self, data: bytes):
        """
        Writes 'data' to the serialport

        Arguments:
        data -- data to write, must be bytes
        """
        self.serial.write(data)
        self.serial.flush()

    def open(self):
        """Opens the serialport, does nothing if it is already closed"""
        if not self.status:
            self.serial.open()

    def close(self):
        """Closes the serialport, does nothing if it is already closed"""
        if self.status:
            self.serial.close()

    def __del__(self):
        if self.serial:
            self.serial.close()
