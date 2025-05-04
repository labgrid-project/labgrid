import attr

from ..factory import target_factory
from ..step import step
from .common import Driver
from ..exceptions import InvalidConfigError
from ..util.managedfile import ManagedFile
from ..util.helper import processwrapper
from ..resource.udev import AndroidUSBFastboot
from ..resource.fastboot import AndroidNetFastboot
from ..resource.remote import RemoteAndroidUSBFastboot, RemoteAndroidNetFastboot


@target_factory.reg_driver
@attr.s(eq=False)
class AndroidFastbootDriver(Driver):
    bindings = {
        "fastboot": {AndroidUSBFastboot, RemoteAndroidUSBFastboot,
                     AndroidNetFastboot, RemoteAndroidNetFastboot},
    }

    boot_image = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    flash_images = attr.ib(
        default={},
        validator=attr.validators.optional(attr.validators.instance_of(dict))
    )
    sparse_size = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('fastboot')
        else:
            self.tool = 'fastboot'

    def _get_fastboot_prefix(self):
        if isinstance(self.fastboot, (AndroidUSBFastboot, RemoteAndroidUSBFastboot)):
            option = f"usb:{self.fastboot.path}"
        else:
            option = f"{self.fastboot.protocol}:{self.fastboot.address}:{self.fastboot.port}"

        prefix = self.fastboot.command_prefix + [ self.tool, "-s", option ]

        if self.sparse_size is not None:
            prefix += ["-S", self.sparse_size]

        return prefix

    @staticmethod
    def _filter_fastboot_output(output, prefix='(bootloader) '):
        """
        Splits output by '\n' and returns only elements starting with prefix. The prefix is
        removed.
        """
        return [line[len(prefix):] for line in output.split('\n') if line.startswith(prefix)]

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(title='call', args=['args'])
    def __call__(self, *args):
        processwrapper.check_output(
            self._get_fastboot_prefix() + list(args),
            print_on_silent_log=True
        )

    @Driver.check_active
    @step(args=['filename'])
    def boot(self, filename=None):
        if filename is None:
            if self.boot_image is None:
                raise InvalidConfigError("No boot_image set")

            filename = self.target.env.config.get_image_path(self.boot_image)

        mf = ManagedFile(filename, self.fastboot)
        mf.sync_to_resource()
        self("boot", mf.get_remote_path())

    @Driver.check_active
    @step(args=['partition', 'filename'])
    def flash(self, partition, filename=None):
        if filename is None:
            try:
                image_key = self.flash_images[partition]
            except KeyError:
                raise InvalidConfigError(f"Partition {partition} not in flash_images")

            filename = self.target.env.config.get_image_path(image_key)

        mf = ManagedFile(filename, self.fastboot)
        mf.sync_to_resource()
        self("flash", partition, mf.get_remote_path())

    @Driver.check_active
    @step()
    def flash_all(self):
        for partition in self.flash_images.keys():
            self.flash(partition)

    @Driver.check_active
    @step(args=['partition'])
    def erase(self, partition):
        self('erase', partition)

    @Driver.check_active
    @step(args=['cmd'])
    def run(self, cmd):
        self("oem", "exec", "--", cmd)

    @Driver.check_active
    @step(title='continue')
    def continue_boot(self):
        self("continue")

    @Driver.check_active
    @step(args=['var'])
    def getvar(self, var):
        """Return variable value via 'fastboot getvar <var>'."""
        if var == 'all':
            raise NotImplementedError('Retrieving a list of all variables is not supported yet')

        cmd = ['getvar', var]
        output = processwrapper.check_output(self._get_fastboot_prefix() + cmd)
        values = AndroidFastbootDriver._filter_fastboot_output(
            output, f'{var}: '
        )
        assert len(values) == 1, 'fastboot did not return exactly one line'
        return values[0]

    @Driver.check_active
    @step(args=['var'])
    def oem_getenv(self, var):
        """Return barebox environment variable value via 'fastboot oem getenv <var>'."""
        cmd = ['oem', 'getenv', var]
        output = processwrapper.check_output(self._get_fastboot_prefix() + cmd)
        values = AndroidFastbootDriver._filter_fastboot_output(output)
        assert len(values) == 1, 'fastboot did not return exactly one line'
        return values[0]
