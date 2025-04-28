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
        'loader': {'IMXUSBLoader', 'NetworkIMXUSBLoader'},
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


@target_factory.reg_driver
@attr.s(eq=False)
class SunxiUSBDriver(Driver, BootstrapProtocol):
    bindings = {
        "loader": {"SunxiUSBLoader", "NetworkSunxiUSBLoader"},
    }

    loadaddr = attr.ib(validator=attr.validators.instance_of(int))
    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('sunxi-fel')
        else:
            self.tool = 'sunxi-fel'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    def _run_tool(self, *part):
        args = ['-d', '%s:%s' % (self.loader.busnum, self.loader.devnum)]
        cmd = ['sunxi-fel'] + args + list(part)

        processwrapper.check_output(
            self.loader.command_prefix + cmd,
            print_on_silent_log=True
        )

    @Driver.check_active
    @step(args=['filename', 'phase'])
    def load(self, filename=None, phase=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.loader)
        mf.sync_to_resource()

        pathname = mf.get_remote_path()
        if phase == 'spl':
            self._run_tool('spl', pathname)
        else:
            self._run_tool('write', '%#x' % self.loadaddr, pathname)

    @Driver.check_active
    @step()
    def execute(self):
        self._run_tool('exe', '%#x' % self.loadaddr)


@target_factory.reg_driver
@attr.s(eq=False)
class TegraUSBDriver(Driver, BootstrapProtocol):
    bindings = {
        'loader': {'TegraUSBLoader', 'NetworkTegraUSBLoader'},
    }

    loadaddr = attr.ib(validator=attr.validators.instance_of(int))
    bct = attr.ib(validator=attr.validators.instance_of(str))
    usb_path = attr.ib(validator=attr.validators.instance_of(str))
    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('tegrarcm')
        else:
            self.tool = 'tegrarcm'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None, phase=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.loader)
        mf.sync_to_resource()

        pathname = mf.get_remote_path()
        args = [self.tool, '--bct=' + self.bct,
               f'--bootloader={pathname}',
               f'--loadaddr={self.loadaddr:#08x}',
               '--usb-port-path', self.usb_path]

        processwrapper.check_output(
            self.loader.command_prefix + args,
            print_on_silent_log=True
        )

    @Driver.check_active
    @step()
    def execute(self):
        """The load() method automatically executes, so this does nothing"""
        pass


@target_factory.reg_driver
@attr.s(eq=False)
class SamsungUSBDriver(Driver, BootstrapProtocol):
    bindings = {
        'loader': {'SamsungUSBLoader', 'NetworkSamsungUSBLoader'},
    }

    bl1 = attr.ib(validator=attr.validators.instance_of(str))
    bl1_loadaddr = attr.ib(validator=attr.validators.instance_of(int))
    spl_loadaddr = attr.ib(validator=attr.validators.instance_of(int))
    loadaddr = attr.ib(validator=attr.validators.instance_of(int))
    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('smdk-usbdl')
        else:
            self.tool = 'smdk-usbdl'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None, phase=None):
        if filename is None and phase == 'bl1':
            filename = self.bl1
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.loader)
        mf.sync_to_resource()

        if phase == 'bl1':
            addr = self.bl1_loadaddr
        elif phase == 'spl':
            addr = self.spl_loadaddr
        elif phase in (None, 'u-boot'):
            addr = self.loadaddr
        else:
            raise ValueError(f"Unknown phase '{phase}'")
        pathname = mf.get_remote_path()
        #time.sleep(0.5)

        args = [self.tool, '-a', f'{addr:x}',
                '-b', f'{self.loader.busnum:03d}',
                '-d', f'{self.loader.devnum:03d}',
                '-f', pathname]

        processwrapper.check_output(
            self.loader.command_prefix + args,
            #print_on_silent_log=True
        )

    @Driver.check_active
    @step()
    def execute(self):
        """The load() method automatically executes, so this does nothing"""
        pass
