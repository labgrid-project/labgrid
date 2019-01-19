import attr

from ..factory import target_factory
from ..protocol import LedProtocol, CommandProtocol
from .common import Driver

@target_factory.reg_driver
@attr.s(cmp=False)
class LedDriver(Driver, LedProtocol):
    bindings = { "command": CommandProtocol }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def led_fn(self, name):
        return "/sys/class/leds/"+name+"/brightness"

    @Driver.check_active
    def write_brightness(self, name, val):
        stdout, stderr, returncode = self.command.run('echo '+str(int(val))+' > "'+self.led_fn(name)+'"')
        assert returncode == 0
        assert not stdout
        assert not stderr

    @Driver.check_active
    def get_brightness(self, name):
        stdout, stderr, returncode = self.command.run('cat "'+self.led_fn(name)+'"')
        assert returncode == 0
        assert stdout
        assert not stderr
        return int(stdout[0])

    @Driver.check_active
    def set_brightness(self, name, val):
        self.write_brightness(name, val)
        assert int(val) == int(self.get_brightness(name))
