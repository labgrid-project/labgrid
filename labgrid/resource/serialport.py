from .resource import Resource
from serial import Serial

class SerialPort(Resource):
    def __init__(self, target, port, speed=115200):
        super(SerialPort, self).__init__()
        self.serial = Serial(port, speed)
        self.target = target
        self.target.resources.append(self)

    def read(self):
        return self.serial.read()

    def write(self, data):
        self.serial.write(data)

    def __del__(self):
        self.serial.close()

    def __repr__():
        return "{}"
