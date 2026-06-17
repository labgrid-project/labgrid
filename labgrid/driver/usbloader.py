import subprocess
import warnings
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
        self.tool = self.target.get_tool('mxs-usb-loader')

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
    verify = attr.ib(default=True, validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.tool = self.target.get_tool('imx-usb-loader')

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

        command = [self.tool, "-p", str(self.loader.path)]
        if self.verify:
            command.append("-c")
        command.append(mf.get_remote_path())

        processwrapper.check_output(
            self.loader.command_prefix + command,
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
        tools = {}
        if self.target.env:
            tools = self.target.env.config.data.get('tools') or {}
        if 'rkdeveloptool' not in tools and 'rk-usb-loader' in tools:
            # Backward compatibility: the rkdeveloptool binary used to be
            # configured under the (misnamed) 'rk-usb-loader' tools key, which
            # is now used by the RKBootstrapDriver instead.
            warnings.warn(
                "Configuring rkdeveloptool under the 'rk-usb-loader' tools key is "
                "deprecated, use the 'rkdeveloptool' key instead",
                DeprecationWarning,
            )
            self.tool = self.target.get_tool('rk-usb-loader')
        else:
            self.tool = self.target.get_tool('rkdeveloptool')

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
class RKBootstrapDriver(Driver, BootstrapProtocol):
    """The RKBootstrapDriver uploads a combined barebox image into a Rockchip
    SoC in MaskROM mode using barebox's ``rk-usb-loader`` tool.

    In contrast to the :any:`RKUSBDriver` (which uses rkdeveloptool's ``db`` and
    ``wl`` commands to flash a bootloader to storage), this driver loads the
    image into RAM and executes it, i.e. it performs a true bootstrap.
    """
    bindings = {
        "loader": {"RKUSBLoader", "NetworkRKUSBLoader"},
    }

    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.tool = self.target.get_tool('rk-usb-loader')

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

        timeout = Timeout(3.0)
        while True:
            try:
                processwrapper.check_output(
                    self.loader.command_prefix +
                    [self.tool, mf.get_remote_path()],
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
        self.tool = self.target.get_tool('uuu-loader')

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
        self.tool = self.target.get_tool('imx_usb')

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
