from importlib import import_module
import attr
import serial
import serial.rfc2217

from ..factory import target_factory
from .common import Driver
from ..resource import SerialPort
from ..util.proxy import proxymanager


@target_factory.reg_driver
@attr.s(eq=False)
class ModbusRTUDriver(Driver):
    bindings = {"resource": {"SerialPort", "NetworkSerialPort"}}

    timeout = attr.ib(default=0.25, validator=attr.validators.instance_of(float))
    address = attr.ib(default=0, validator=attr.validators.instance_of(int))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._modbus = import_module("minimalmodbus")
        self.instrument = None

    def on_activate(self):
        if isinstance(self.resource, SerialPort):
            self.instrument = self._modbus.Instrument(
                self.resource.port, self.address, debug=False
            )
        else:
            if self.resource.protocol == "rfc2217":
                serial_if = serial.rfc2217.Serial()
            elif self.resource.protocol == "raw":
                serial_if = serial.serial_for_url("socket://", do_not_open=True)
            else:
                raise Exception("ModbusRTUDriver: unknown protocol")

            host, port = proxymanager.get_host_and_port(self.resource)
            if self.resource.protocol == "rfc2217":
                serial_if.port = (
                    f"rfc2217://{host}:{port}?ign_set_control&timeout={self.timeout}"
                )
            elif self.resource.protocol == "raw":
                serial_if.port = f"socket://{host}:{port}/"
            else:
                raise Exception("ModbusRTUDriver: unknown protocol")
            serial_if.baudrate = self.resource.speed
            serial_if.open()

            self.instrument = self._modbus.Instrument(
                serial_if,
                slaveaddress=self.address,
                close_port_after_each_call=True,
                debug=False,
            )

        self.instrument.serial.baudrate = self.resource.speed
        self.instrument.serial.timeout = self.timeout

        self.instrument.mode = self._modbus.MODE_RTU
        self.instrument.clear_buffers_before_each_transaction = True

    def on_deactivate(self):
        self.instrument = None

    def read_bit(self, *args, **kwargs):
        return self.instrument.read_bit(*args, **kwargs)

    def write_bit(self, *args, **kwargs):
        return self.instrument.write_bit(*args, **kwargs)

    def read_bits(self, *args, **kwargs):
        return self.instrument.read_bits(*args, **kwargs)

    def write_bits(self, *args, **kwargs):
        return self.instrument.write_bits(*args, **kwargs)

    def read_long(self, *args, **kwargs):
        return self.instrument.read_long(*args, **kwargs)

    def write_long(self, *args, **kwargs):
        return self.instrument.write_long(*args, **kwargs)

    def read_float(self, *args, **kwargs):
        return self.instrument.read_float(*args, **kwargs)

    def write_float(self, *args, **kwargs):
        return self.instrument.write_float(*args, **kwargs)

    def read_string(self, *args, **kwargs):
        return self.instrument.read_string(*args, **kwargs)

    def write_string(self, *args, **kwargs):
        return self.instrument.write_string(*args, **kwargs)

    def read_register(self, *args, **kwargs):
        return self.instrument.read_register(*args, **kwargs)

    def write_register(self, *args, **kwargs):
        return self.instrument.write_register(*args, **kwargs)

    def read_registers(self, *args, **kwargs):
        return self.instrument.read_registers(*args, **kwargs)

    def write_registers(self, *args, **kwargs):
        return self.instrument.write_registers(*args, **kwargs)
