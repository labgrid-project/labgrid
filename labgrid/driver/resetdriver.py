import time

import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol, ResetProtocol, BootCfgProtocol
from ..resource.remote import NetworkUSBResetPort
from ..resource.udev import USBResetPort
from ..step import step
from .common import Driver
from ..util.helper import processwrapper

@target_factory.reg_driver
@attr.s(eq=False)
class DigitalOutputResetDriver(Driver, ResetProtocol):
    """DigitalOutputResetDriver - Driver using a DigitalOutput to reset the
    target"""
    bindings = {"output": DigitalOutputProtocol, }
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step()
    def reset(self):
        self.output.set(True)
        time.sleep(self.delay)
        self.output.set(False)

@target_factory.reg_driver
@attr.s(eq=False)
class BCUResetDriver(Driver, ResetProtocol, BootCfgProtocol):
    """BCUResetDriver - Driver using https://github.com/NXPmicro/bcu and board
    serial port as USBResetPort to reset the target into different states"""

    bindings = {
       "port": {USBResetPort, NetworkUSBResetPort}, 
    }

    delay = attr.ib(default=1000, validator=attr.validators.instance_of(int))
    emmc_cfg = attr.ib(default="emmc", validator=attr.validators.instance_of(str))
    sd_cfg = attr.ib(default="sd", validator=attr.validators.instance_of(str))
    usb_cfg = attr.ib(default="usb", validator=attr.validators.instance_of(str))
    qspi_cfg = attr.ib(default="", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.tool = 'bcu'

    @Driver.check_active
    @step()
    def reset(self, mode=""):
        cmd = self.port.command_prefix + [
            self.tool,
            "reset", mode,
            "-board={}".format(self.port.board),
            "-id={}".format(self.port.path),
            "-delay={}".format(str(self.delay)),
        ]
        try:
            print(str(processwrapper.check_output(cmd).decode()))
        except subprocess.CalledProcessError as e:
            raise  
            
    @Driver.check_active
    @step()
    def sd(self):
        self.reset(self.sd_cfg)

    @Driver.check_active
    @step()
    def emmc(self):
        self.reset(self.emmc_cfg)

    @Driver.check_active
    @step()
    def usb(self):
        self.reset(self.usb_cfg)

    @Driver.check_active
    @step()
    def qspi(self):
        if not self.qspi_cfg:
            print("QSPI mode is not set, board is reseting in current mode")
        self.reset(self.qspi_cfg)

