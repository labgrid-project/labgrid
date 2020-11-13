# pylint: disable=no-member
import attr

from ..factory import target_factory
from ..step import step
from .common import Driver
from ..util.managedfile import ManagedFile
from ..util.helper import processwrapper


@target_factory.reg_driver
@attr.s(eq=False)
class AndroidFastbootDriver(Driver):
    bindings = {
        "fastboot": {"AndroidFastboot", "NetworkAndroidFastboot"},
    }

    image = attr.ib(default=None)
    sparse_size = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('fastboot') or 'fastboot'
        else:
            self.tool = 'fastboot'

    def _get_fastboot_prefix(self):
        prefix = self.fastboot.command_prefix+[
            self.tool,
            "-i", hex(self.fastboot.vendor_id),
            "-s", "usb:{}".format(self.fastboot.path),
        ]

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
    def boot(self, filename):
        mf = ManagedFile(filename, self.fastboot)
        mf.sync_to_resource()
        self("boot", mf.get_remote_path())

    @Driver.check_active
    @step(args=['partition', 'filename'])
    def flash(self, partition, filename):
        mf = ManagedFile(filename, self.fastboot)
        mf.sync_to_resource()
        self("flash", partition, mf.get_remote_path())

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
            output, '{}: '.format(var)
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
