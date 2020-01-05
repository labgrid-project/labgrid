# pylint: disable=no-member
"""The SSHDriver uses SSH as a transport to implement CommandProtocol and FileTransferProtocol"""
import logging
import os
import shutil
import subprocess
import selectors
import tempfile

import attr
from pexpect import TIMEOUT

from ..factory import target_factory
from ..protocol import CommandProtocol, FileTransferProtocol, BackgroundProcessProtocol
from ..resource import NetworkService
from .commandmixin import CommandMixin
from .common import Driver
from ..step import step
from .exception import ExecutionError
from ..util.timeout import Timeout


@target_factory.reg_driver
@attr.s(eq=False)
class SSHDriver(CommandMixin, Driver, CommandProtocol, FileTransferProtocol,
                BackgroundProcessProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    bindings = {"networkservice": NetworkService, }
    priorities = {CommandProtocol: 10, FileTransferProtocol: 10}
    keyfile = attr.ib(default="", validator=attr.validators.instance_of(str))
    stderr_merge = attr.ib(default=False, validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}({})".format(self, self.target))
        self.background_processes = []

    def on_activate(self):
        self.ssh_prefix = "-o LogLevel=ERROR"
        if self.keyfile:
            keyfile_path = self.keyfile
            if self.target.env:
                keyfile_path = self.target.env.config.resolve_path(self.keyfile)
            self.ssh_prefix += " -i {}".format(keyfile_path)
        self.ssh_prefix += " -o PasswordAuthentication=no" if (
            not self.networkservice.password) else ""
        self.control = self._check_master()
        self.ssh_prefix += " -F /dev/null"
        self.ssh_prefix += " -o ControlPath={}".format(
            self.control
        ) if self.control else ""

    def on_deactivate(self):
        while self.background_processes:
            proc = self.background_processes.pop()
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

        self._cleanup_own_master()

    def _start_own_master(self):
        """Starts a controlmaster connection in a temporary directory."""
        self.tmpdir = tempfile.mkdtemp(prefix='labgrid-ssh-tmp-')
        control = os.path.join(
            self.tmpdir, 'control-{}'.format(self.networkservice.address)
        )
        # use sshpass if we have a password
        sshpass = "sshpass -e " if self.networkservice.password else ""
        args = ("{}ssh -f {} -x -o ConnectTimeout=30 -o ControlPersist=300 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=15 -MN -S {} -p {} {}@{}").format( # pylint: disable=line-too-long
            sshpass, self.ssh_prefix, control, self.networkservice.port,
            self.networkservice.username, self.networkservice.address).split(" ")

        env = os.environ.copy()
        if self.networkservice.password:
            env['SSHPASS'] = self.networkservice.password
        self.process = subprocess.Popen(args, env=env)

        try:
            if self.process.wait(timeout=30) != 0:
                raise ExecutionError(
                    "failed to connect to {} with {} and {}".
                    format(self.networkservice.address, args, self.process.wait())
                )
        except subprocess.TimeoutExpired:
            raise ExecutionError(
                "failed to connect to {} with {} and {}".
                format(self.networkservice.address, args, self.process.wait())
                )

        if not os.path.exists(control):
            raise ExecutionError(
                "no control socket to {}".format(self.networkservice.address)
            )

        self.logger.debug('Connected to %s', self.networkservice.address)

        return control

    def _check_master(self):
        args = [
            "ssh", "-O", "check", "{}@{}".format(
                self.networkservice.username, self.networkservice.address
            )
        ]
        check = subprocess.call(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if check == 0:
            return ""

        return self._start_own_master()

    @Driver.check_active
    @step(args=['cmd'], result=True)
    def run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=None): # pylint: disable=unused-argument
        """Execute `cmd` on the target.

        This method runs the specified `cmd` as a command on its target.
        It uses the ssh shell command to run the command and parses the exitcode.
        cmd - command to be run on the target

        returns:
        (stdout, stderr, returncode)
        """
        return self._run(cmd, codec=codec, decodeerrors=decodeerrors)

    def _run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=None): # pylint: disable=unused-argument
        timeout_ = None if timeout is None else Timeout(float(timeout))

        process = self._run_as_background_process(cmd)
        read_timeout = timeout_.remaining if timeout_ else None
        stdout, stderr = self._read_from_background_process(process, timeout=read_timeout)

        if timeout_ and timeout_.expired:
            raise TIMEOUT("Timeout of {} seconds exceeded while executing {}"
                          .format(timeout, process))

        exitcode = self.poll_background_process(process)
        assert exitcode is not None

        stdout = stdout.split('\n')[:-1]
        stderr = stderr.split('\n')[:-1]

        return (stdout, stderr, exitcode)

    @Driver.check_active
    @step(args=['command'], result=True)
    def run_as_background_process(self, command):
        """
        Runs the given `command` as a background process and immediately return a process handle.

        Args:
            command (str): the command to run in background

        Returns:
            process handle (Popen)
        """
        return self._run_as_background_process(command)

    def _run_as_background_process(self, command):
        complete_cmd = "ssh -x {prefix} -p {port} {user}@{host} {cmd}".format(
            user=self.networkservice.username,
            host=self.networkservice.address,
            cmd=command,
            prefix=self.ssh_prefix,
            port=self.networkservice.port
        ).split(' ')
        self.logger.debug("Sending command: %s", complete_cmd)
        if self.stderr_merge:
            stderr_pipe = subprocess.STDOUT
        else:
            stderr_pipe = subprocess.PIPE
        try:
            proc = subprocess.Popen(complete_cmd, stdout=subprocess.PIPE, stderr=stderr_pipe)
            self.background_processes.append(proc)
            return proc
        except:
            raise ExecutionError(
                "error executing command: {}".format(complete_cmd)
            )

    @Driver.check_active
    @step(args=['process', 'timeout'], result=True)
    def read_from_background_process(self, process, *, timeout=0):
        """
        Read stdout/stderr of background process until timeout. For timeout=0 (default) the call
        won't block and will return stdout/stderr until current EOF. For timeout=None the call
        will block until the process has terminated. Returns a tuple (stdout, stderr).
        Raises ExecutionError if process is not known.

        Args:
            process (Popen): process handle
            timeout (int or None): will block until timeout is exceeded or process terminates,
                                   timeout=0 returns immediately (default), timeout=None blocks
                                   until process terminates

        Returns:
            (stdout (str), stderr (str))
        """

        return self._read_from_background_process(process, timeout=timeout)

    def _read_from_background_process(self, process, *, timeout=0):
        assert isinstance(process, subprocess.Popen)
        if process not in self.background_processes:
            raise ExecutionError('Unknown process handle')

        timeout_ = None if timeout is None or timeout <= 0 else Timeout(float(timeout))
        output = {
            process.stdout: [],
            process.stderr: [],
        }

        with selectors.PollSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            selector.register(process.stderr, selectors.EVENT_READ)

            while selector.get_map():
                select_timeout = timeout_.remaining if timeout_ else timeout
                ready = selector.select(timeout=select_timeout)

                # return as soon as there is nothing left to read
                if not ready:
                    break

                for key, _ in ready:
                    if key.fileobj in (process.stdout, process.stderr):
                        data = os.read(key.fd, 32768)
                        if not data:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        output[key.fileobj].append(data)

        # read until EOF, decoding should now work safely
        stdout = b''.join(output[process.stdout])
        stdout = self._translate_newlines(stdout)

        stderr = b''.join(output[process.stderr])
        stderr = self._translate_newlines(stderr)

        return (stdout, stderr)

    @Driver.check_active
    def poll_background_process(self, process):
        """
        Check if background process has terminated. Returns exitcode if process has terminated
        otherwise None. Raises ExecutionError if process is not known.

        Args:
            process (Popen): process handle, type implementation defined

        Returns:
            exit code if process terminated otherwise None
        """
        assert isinstance(process, subprocess.Popen)
        if process not in self.background_processes:
            raise ExecutionError('Unknown process handle')

        return process.poll()

    def _translate_newlines(self, out, codec="utf-8", decodeerrors="strict"):
        # TODO: use codec/decodeerrors from instance variable once all drivers are adjusted that
        # way
        out = out.decode(codec, decodeerrors)
        out = out.replace('\r\n', '\n').replace('\r', '\n')
        return out

    def get_status(self):
        """The SSHDriver is always connected, return 1"""
        return 1

    @Driver.check_active
    @step(args=['filename', 'remotepath'])
    def put(self, filename, remotepath=''):
        transfer_cmd = "scp {prefix} -P {port} {filename} {user}@{host}:{remotepath}".format(
            filename=filename,
            user=self.networkservice.username,
            host=self.networkservice.address,
            remotepath=remotepath,
            prefix=self.ssh_prefix,
            port=self.networkservice.port
        ).split(' ')
        try:
            sub = subprocess.call(
                transfer_cmd
            )  #, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )
        if sub != 0:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )

    @Driver.check_active
    @step(args=['filename', 'destination'])
    def get(self, filename, destination="."):
        transfer_cmd = "scp {prefix} -P {port} {user}@{host}:{filename} {destination}".format(
            filename=filename,
            user=self.networkservice.username,
            host=self.networkservice.address,
            prefix=self.ssh_prefix,
            port=self.networkservice.port,
            destination=destination
        ).split(' ')
        try:
            sub = subprocess.call(
                transfer_cmd
            )  #, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )
        if sub != 0:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )

    def _cleanup_own_master(self):
        """Exit the controlmaster and delete the tmpdir"""
        complete_cmd = "ssh -x -o ControlPath={cpath} -O exit -p {port} {user}@{host}".format(
            cpath=self.control,
            port=self.networkservice.port,
            user=self.networkservice.username,
            host=self.networkservice.address
        ).split(' ')
        res = subprocess.call(
            complete_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if res != 0:
            self.logger.info("Socket already closed")
        shutil.rmtree(self.tmpdir)
