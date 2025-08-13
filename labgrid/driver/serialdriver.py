import attr
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
    bindings = {"port": {"SerialPort", "NetworkSerialPort"}, }

    txdelay = attr.ib(default=0.0, validator=attr.validators.instance_of(float))
    timeout = attr.ib(default=3.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
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

    @Driver.check_bound
    def get_export_vars(self):
        export_vars = {
            "speed": str(self.port.speed)
        }
        if isinstance(self.port, SerialPort):
            export_vars["port"] = self.port.port
        else:
            host, port = proxymanager.get_host_and_port(self.port)
            export_vars["host"] = host
            export_vars["port"] = str(port)
            export_vars["protocol"] = self.port.protocol
        return export_vars

    def _read(self, size: int = 1, timeout: float = 0.0, max_size: int = None):
        """
        Reads 'size' or more bytes from the serialport

        Keyword Arguments:
        size -- amount of bytes to read, defaults to 1
        max_size -- maximal amount of bytes to read, values 'None' or '0' do not restrict the read
                    length, defaults to None
        if size == max_size: read and return exactly size = max_size bytes
        """
        reading = max(size, self.serial.in_waiting)
        if max_size:  # limit reading to max_size if provided
            reading = min(reading, max_size)
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
        """Opens the serialport, does nothing if it is already open"""
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

    def __str__(self):
        return f"SerialDriver({self.target.name})"
