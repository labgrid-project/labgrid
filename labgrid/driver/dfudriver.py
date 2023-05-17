import attr

from ..factory import target_factory
from ..step import step
from .common import Driver
from ..util.managedfile import ManagedFile
from ..util.helper import processwrapper


@target_factory.reg_driver
@attr.s(eq=False)
class DFUDriver(Driver):
    bindings = {
        "dfu": {"DFUDevice", "NetworkDFUDevice"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('dfu-util')
        else:
            self.tool = 'dfu-util'

    def _get_dfu_prefix(self):
        return self.dfu.command_prefix + [
            self.tool,
            "-p", self.dfu.path,
        ]

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['altsetting', 'filename'])
    def download(self, altsetting, filename):
        mf = ManagedFile(filename, self.dfu)
        mf.sync_to_resource()

        processwrapper.check_output(
            self._get_dfu_prefix() + ['--alt', str(altsetting), '--download', mf.get_remote_path()],
            print_on_silent_log=True
        )

    @step()
    def detach(self, altsetting):
        processwrapper.check_output(
            self._get_dfu_prefix() + ['--alt', str(altsetting), '--detach']
        )

    @step()
    def list(self):
        processwrapper.check_output(
            self._get_dfu_prefix() + ['--list'],
            print_on_silent_log=True
        )
