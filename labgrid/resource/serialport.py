from .resource import Resource
import serial
import attr

@attr.s
class SerialPort(Resource):
    target = attr.ib()
    port = attr.ib(validator=attr.validators.instance_of(str))
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))

    def __attrs_post_init__(self):
        super(SerialPort, self).__init__(self.target, self)
        self.serial = serial.Serial(self.port, self.speed)

    def read(self):
        return self.serial.read()

    def write(self, data: bytes):
        self.serial.write(data)

    def __del__(self):
        self.serial.close()
