import subprocess
from threading import Thread
import time

import attr
from .common import Driver
from ..factory import target_factory
from ..var_dict import get_var
from ..step import step
from ..util.helper import processwrapper, ProcessRunner
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

    Variables:
        em100-trace (str): Filename for trace file, if required
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
        self._trace = get_var('em100-trace')

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

        # For trace mode, start a process which will run for the duration of
        # the Labgrid client, all going well
        if self._trace:
            cmd.append('-t')
            logfile = open(self._trace, 'w')
            self._thread = Thread(target=self.monitor_thread,
                                  args=(cmd, logfile))
            self._thread.daemon = True
            self._thread.start()
        else:
            processwrapper.check_output(cmd)

    def __str__(self):
        return f'SFEmulatorDriver({self.emul.serial})'

    def monitor_thread(self, cmd, logfile):
        """Thread to monitor the em100 process

        This is mostly just here to check if it dies, so a useful error can be
        shown.

        Args:
            cmd (list of str): Command to run
            logfile (file): Output file for trace log
        """
        proc = ProcessRunner(cmd, stdin=subprocess.DEVNULL, stdout=logfile)
        while True:
            if proc.check():
                break
            time.sleep(.1)
        try:
            proc.kill()
            proc.finish()
        except subprocess.CalledProcessError as exc:
            # If there is something wrong, the error will be in the logfile, so
            # print it out
            print('em100 failed', exc.returncode)
            with open(self._trace, 'r') as inf:
                print('err', inf.read(1024))
