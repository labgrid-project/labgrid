from ..resource import SerialPort
import pexpect
import attr

@attr.s
class ConsoleProtocol(object):
    target = attr.ib()

    def __attrs_post_init__(self):
        super(ConsoleProtocol, self).__init__(self.target, self)
        self.port = self.target.get_resource(SerialPort)[0]
        self.expect = fdpexpect.fdspawn(self.port)

    def run(self, command: str):
        self.port.write(command + '\n')
        return self.read()


