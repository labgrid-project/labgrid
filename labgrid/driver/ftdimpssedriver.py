import attr
from ..factory import target_factory
from .common import Driver
from ..resource.remote import NetworkFTDIPort
from ..util.agentwrapper import AgentWrapper

SUPPORTED_FTDIS = [
    "2232",
    "2232h",
    "4232h",
]
FTDI_INTERFACE_JTAG = 1
FTDI_INTERFACE_I2C = 2

@target_factory.reg_driver
@attr.s(eq=False)
class FtdiMpsseDriver(Driver):
    """
    Hardware-level driver executing directly on the Exporter.
    """
    bindings = {
        "port": NetworkFTDIPort,
    }

    PROFILES = {
        "2232": {
            "url_base": "ftdi://ftdi:2232",
            "mask": (1 << 13) | (1 << 14),
            "val": (1 << 13),
        },
        "2232h": {
            "url_base": "ftdi://ftdi:2232h",
            "mask": (1 << 13) | (1 << 14), # FTDI_MODE0, FTDI_MODE1
            "val": (1 << 13)
        },
        "4232h": {
            "url_base": "ftdi://ftdi:4232h",
            "mask": 1 << 5, # FTDI_MODE0
            "val": 1 << 5
        },
    }

    ftdichip = attr.ib(default="2232h", validator=attr.validators.in_(SUPPORTED_FTDIS))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None
        self.proxy = None

    def on_activate(self):
        host = self.port.host if hasattr(self.port, "host") else None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('ftdimpsse')

    def on_deactivate(self):
        if self.wrapper:
            self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    def _get_cfg(self):
        return self.PROFILES.get(self.ftdichip, self.PROFILES["2232h"])

    def _get_url(self, interface_index):
        cfg = self._get_cfg()
        base = cfg["url_base"]
        return f"{base}/{interface_index}"

    def _get_jtag_url(self):
        return self._get_url(interface_index=FTDI_INTERFACE_JTAG)

    def _get_i2c_url(self):
        return self._get_url(interface_index=FTDI_INTERFACE_I2C)

    @Driver.check_active
    def dump_eeprom(self):
        url = self._get_jtag_url()
        return self.proxy.dump_eeprom(url)

    @Driver.check_active
    def i2cdetect(self):
        url = self._get_i2c_url()
        cfg = self._get_cfg()
        mask = cfg.get("mask", 0)
        val = cfg.get("val", 0)
        return self.proxy.i2cdetect(url, mask, val)

    @Driver.check_active
    def i2ctransfer(self, args):
        url = self._get_i2c_url()
        cfg = self._get_cfg()
        mask = cfg.get("mask", 0)
        val = cfg.get("val", 0)
        return self.proxy.i2ctransfer(url, mask, val, args)

    @Driver.check_active
    def i2cread(self, chip_addr: str, reg_addr: str) -> int:
        args = [chip_addr, "w1", reg_addr, "r1"]
        result = self.proxy.i2ctransfer(self._get_i2c_url(), self._get_cfg()["mask"], self._get_cfg()["val"], args)
        if isinstance(result, (list, tuple)) and len(result) > 0:
            result = result[0]
        if isinstance(result, bytes):
            result = result.decode('utf-8')
        if isinstance(result, str) and result.lower().startswith("0x"):
            return int(result, 16)
        return int(result)
