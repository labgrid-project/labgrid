import attr
import pexpect
from ..protocol import ConsoleProtocol
from ..resource import SerialPort
from .exception import NoResourceException

@attr.s
class SerialDriver(ConsoleProtocol):
    """
    Driver implementing the ConsoleProtocol interface over a SerialPort connection
    """
    target = attr.ib()

    def __attrs_post_init__(self):
        self.port = self.target.get_resource(SerialPort) #pylint: disable=no-member,attribute-defined-outside-init
        if not self.port:
            raise NoResourceException("Target has no SerialPort Resource")
        self.target.drivers.append(self) #pylint: disable=no-member
        self.port.open()
        self.status = 1 #pylint: disable=attribute-defined-outside-init


    def write(self, data: bytes):
        """

        Arguments:
        data -- data to be send
        """
        self.port.write(data)
        self.port.flush()

    def read(self):
        """
        Reads data from the underlying port
        """
        return self.port.read()
