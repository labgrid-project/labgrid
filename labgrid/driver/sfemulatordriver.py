import attr
from .common import Driver
from ..factory import target_factory
from ..step import step
from ..util.helper import processwrapper
from ..util.managedfile import ManagedFile

@target_factory.reg_driver
@attr.s(eq=False)
class SFEmulatorDriver(Driver):
    """Provides access to em100 features

    Args:
        bindings (dict): driver to use with
        _proc (subprocess.Popen): Process running em100 (used only in trace
            mode)
        _trace (str): Filename of trace file, if enabled
        _thread (Thread): Thread which monitors the subprocess for errors
    """
    bindings = {
        'emul': {'SFEmulator', 'NetworkSFEmulator'},
    }
    trace = attr.ib(default=False, validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('em100')
        else:
            self.tool = 'em100'
        self._trace = None
        self._thread = None

    @Driver.check_active
    @step(title='write_image', args=['filename'])
    def write_image(self, filename):
        '''Write an image to the SPI-flash emulator

        Args:
            filename (str): Filename to write
        '''
        mf = ManagedFile(filename, self.emul)
        mf.sync_to_resource()
        cmd = self.emul.command_prefix + [
            self.tool,
            '-x', str(self.emul.serial),
            '-s',
            '-p', 'LOW',
            '-c', self.emul.chip,
            '-d', mf.get_remote_path(),
            '-r',
        ]

        processwrapper.check_output(cmd)

    def __str__(self):
        return f'SFEmulatorDriver({self.emul.serial})'
