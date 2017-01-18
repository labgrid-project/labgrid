# pylint: disable=no-member
import attr
import subprocess

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..resource.udev import MXSUSBLoader, IMXUSBLoader
from ..step import step
from .common import Driver
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s
class MXSUSBDriver(Driver, BootstrapProtocol):
    bindings = {"loader": MXSUSBLoader, }

    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @step(args=['filename'])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        tool = self.target.env.config.get_tool('mxs-usb-loader')
        subprocess.check_call([tool, "0", filename])

@target_factory.reg_driver
@attr.s
class IMXUSBDriver(Driver, BootstrapProtocol):
    bindings = {"loader": IMXUSBLoader, }

    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @step(args=['filename'])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        tool = self.target.env.config.get_tool('imx-usb-loader')
        raise NotImplementedError("implement call to imx-usb-loader")
        subprocess.check_call([tool, filename])
