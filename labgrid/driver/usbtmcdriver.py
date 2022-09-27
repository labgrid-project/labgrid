from importlib import import_module
from decimal import Decimal
import attr

from .common import Driver
from ..factory import target_factory
from ..exceptions import InvalidConfigError
from ..util.agentwrapper import AgentWrapper, b2s, s2b

@target_factory.reg_driver
@attr.s(eq=False)
class USBTMCDriver(Driver):
    bindings = {
        "tmc": {"USBTMC", "NetworkUSBTMC"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None
        self.backend = None

        assert self.tmc.path.startswith('/dev/usbtmc')
        self.index = int(self.tmc.path[11:], 10)
        assert self.tmc.path == '/dev/usbtmc'+str(self.index)

    def on_activate(self):
        assert self.wrapper is None
        self.wrapper = AgentWrapper(self.tmc.host)

        match = (self.tmc.vendor_id, self.tmc.model_id)
        if match == (0x0957, 0x1798):
            model = 'keysight_dsox2000'
        elif match == (0x0699, 0x0368):
            model = 'tektronix_tds2000'
        else:
            raise InvalidConfigError("Unkown USB TMC device {:04x}:{:04x}".format(*match))

        # TODO: allow backends to register models with other names
        self.backend = import_module(
            f".usbtmc.{model}",
            __package__
        )

    def on_deactivate(self):
        assert self.wrapper is not None
        self.wrapper.close()
        self.wrapper = None
        self.backend = None

    @Driver.check_active
    def command(self, cmd):
        assert isinstance(cmd, str)
        cmd = b2s(cmd.encode('ASCII')+b'\n')
        self.wrapper.usbtmc(self.index, cmd, read=False)

    @Driver.check_active
    def query(self, cmd, binary=False, raw=False):
        assert isinstance(cmd, str)
        cmd = b2s(cmd.encode('ASCII')+b'\n')
        res = s2b(self.wrapper.usbtmc(self.index, cmd, read=True))

        if raw:
            return res

        if binary:
            assert res[0:1] == b'#'
            digits = int(res[1:2], 10)
            count = int(res[2:2+digits], 10)
            return res[2+digits:2+digits+count]

        assert res[-1:] == b'\n'
        return res[:-1].decode('ASCII')

    @Driver.check_active
    def identify(self):
        return self.query('*IDN?')

    @Driver.check_active
    def get_channel_info(self, channel):
        return self.backend.get_channel_info(self, channel)

    @Driver.check_active
    def get_channel_values(self, channel):
        return self.backend.get_channel_values(self, channel)

    @Driver.check_active
    def get_screenshot(self):
        png = getattr(self.backend, 'get_screenshot_png', None)
        tiff = getattr(self.backend, 'get_screenshot_tiff', None)
        if png:
            return 'png', png(self)  # pylint: disable=not-callable
        if tiff:
            return 'tiff', tiff(self)  # pylint: disable=not-callable

        raise InvalidConfigError("get_screenshot_png/_tiff not implemented")

    @Driver.check_active
    def get_bool(self, cmd):
        return bool(int(self.query(cmd).strip()))

    @Driver.check_active
    def get_int(self, cmd):
        return int(self.query(cmd).strip())

    @Driver.check_active
    def get_decimal(self, cmd):
        return Decimal(self.query(cmd).strip())

    @Driver.check_active
    def get_str(self, cmd):
        return self.query(cmd)
