import subprocess
import attr

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..step import step
from .common import Driver
from ..util.managedfile import ManagedFile
from ..util.timeout import Timeout
from ..util.helper import processwrapper


@target_factory.reg_driver
@attr.s(eq=False)
class MXSUSBDriver(Driver, BootstrapProtocol):
    bindings = {
        "loader": {"MXSUSBLoader", "NetworkMXSUSBLoader"},
    }

    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('mxs-usb-loader')
        else:
            self.tool = 'mxs-usb-loader'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.loader)
        mf.sync_to_resource()

        processwrapper.check_output(
            self.loader.command_prefix + [self.tool, "0", mf.get_remote_path()],
            print_on_silent_log=True
        )


@target_factory.reg_driver
@attr.s(eq=False)
class IMXUSBDriver(Driver, BootstrapProtocol):
    bindings = {
        "loader": {"IMXUSBLoader", "NetworkIMXUSBLoader", "MXSUSBLoader", "NetworkMXSUSBLoader"},
    }

    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('imx-usb-loader')
        else:
            self.tool = 'imx-usb-loader'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.loader)
        mf.sync_to_resource()

        processwrapper.check_output(
            self.loader.command_prefix +
            [self.tool, "-p", str(self.loader.path), "-c", mf.get_remote_path()],
            print_on_silent_log=True
        )


@target_factory.reg_driver
@attr.s(eq=False)
class RKUSBDriver(Driver, BootstrapProtocol):
    bindings = {
        "loader": {"RKUSBLoader", "NetworkRKUSBLoader"},
    }

    image = attr.ib(default=None)
    usb_loader = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('rk-usb-loader')
        else:
            self.tool = 'rk-usb-loader'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        if self.target.env:
            usb_loader = self.target.env.config.get_image_path(self.usb_loader)
            mf = ManagedFile(usb_loader, self.loader)
            mf.sync_to_resource()

        timeout = Timeout(3.0)
        while True:
            try:
                processwrapper.check_output(
                    self.loader.command_prefix +
                    [self.tool, 'db', mf.get_remote_path()],
                    print_on_silent_log=True
                )
                break
            except subprocess.CalledProcessError:
                if timeout.expired:
                    raise

        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.loader)
        mf.sync_to_resource()

        timeout = Timeout(3.0)
        while True:
            try:
                processwrapper.check_output(
                    self.loader.command_prefix +
                    [self.tool, 'wl', '0x40', mf.get_remote_path()],
                    print_on_silent_log=True
                )
                break
            except subprocess.CalledProcessError:
                if timeout.expired:
                    raise


@target_factory.reg_driver
@attr.s(eq=False)
class UUUDriver(Driver, BootstrapProtocol):
    bindings = {
        "loader": {"IMXUSBLoader", "NetworkIMXUSBLoader", "MXSUSBLoader", "NetworkMXSUSBLoader"},
    }

    image = attr.ib(default=None)
    script = attr.ib(default='', validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('uuu-loader')
        else:
            self.tool = 'uuu-loader'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.loader)
        mf.sync_to_resource()

        cmd = ['-b', self.script] if self.script else []

        processwrapper.check_output(
            self.loader.command_prefix + [self.tool] + cmd + [mf.get_remote_path()],
            print_on_silent_log=True
        )


@target_factory.reg_driver
@attr.s(eq=False)
class BDIMXUSBDriver(Driver, BootstrapProtocol):
    """
    This is a Driver for the Boundary Devices imx_usb_loader available from
    https://github.com/boundarydevices/imx_usb_loader

    It supports loading the second stage bootloader to a SDP gadget implemented
    by the first stage bootloader in SRAM. Accordingly, the image to upload
    must be specified explicitly.
    """
    bindings = {
        "loader": {"IMXUSBLoader", "NetworkIMXUSBLoader"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('imx_usb')
        else:
            self.tool = 'imx_usb'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename):
        mf = ManagedFile(filename, self.loader)
        mf.sync_to_resource()

        processwrapper.check_output(
            self.loader.command_prefix + [
                self.tool,
                f"--bus={self.loader.busnum}",
                f"--device={self.loader.devnum}",
                mf.get_remote_path(),
            ],
            print_on_silent_log=True
        )
