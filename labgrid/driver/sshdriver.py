# pylint: disable=no-member
"""The SSHDriver uses SSH as a transport to implement CommandProtocol and FileTransferProtocol"""
import contextlib
import logging
import os
import stat
import shutil
import subprocess
import tempfile
import time

import attr

from ..factory import target_factory
from ..protocol import CommandProtocol, FileTransferProtocol
from .commandmixin import CommandMixin
from .common import Driver
from ..step import step
from .exception import ExecutionError
from ..util.helper import get_free_port
from ..util.proxy import proxymanager
from ..util.timeout import Timeout


@target_factory.reg_driver
@attr.s(eq=False)
class SSHDriver(CommandMixin, Driver, CommandProtocol, FileTransferProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    bindings = {"networkservice": "NetworkService", }
    priorities = {CommandProtocol: 10, FileTransferProtocol: 10}
    keyfile = attr.ib(default="", validator=attr.validators.instance_of(str))
    stderr_merge = attr.ib(default=False, validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger(f"{self}({self.target})")
        self._keepalive = None

    def on_activate(self):
        self.ssh_prefix = ["-o", "LogLevel=ERROR"]
        if self.keyfile:
            keyfile_path = self.keyfile
            if self.target.env:
                keyfile_path = self.target.env.config.resolve_path(self.keyfile)
            self.ssh_prefix += ["-i", keyfile_path ]
        if not self.networkservice.password:
            self.ssh_prefix += ["-o", "PasswordAuthentication=no"]

        self.control = self._start_own_master()
        self.ssh_prefix += ["-F", "none"]
        if self.control:
            self.ssh_prefix += ["-o", f"ControlPath={self.control.replace('%', '%%')}"]

        self._keepalive = None
        self._start_keepalive()

    def on_deactivate(self):
        try:
            self._stop_keepalive()
        finally:
            self._cleanup_own_master()

    def _start_own_master(self):
        """Starts a controlmaster connection in a temporary directory."""

        timeout = Timeout(30.0)

        # Retry start of controlmaster, to allow handle failures such as
        # connection refused during target startup
        connect_timeout = round(timeout.remaining)
        while True:
            if connect_timeout == 0:
                raise Exception("Timeout while waiting for ssh connection")
            try:
                return self._start_own_master_once(connect_timeout)
            except ExecutionError as e:
                if timeout.expired:
                    raise e
                time.sleep(0.5)
                connect_timeout = round(timeout.remaining)

    def _start_own_master_once(self, timeout):

        self.tmpdir = tempfile.mkdtemp(prefix='labgrid-ssh-tmp-')
        control = os.path.join(
            self.tmpdir, f'control-{self.networkservice.address}'
        )

        args = ["ssh", "-f", *self.ssh_prefix, "-x", "-o", f"ConnectTimeout={timeout}",
                 "-o", "ControlPersist=300", "-o",
                 "UserKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=no",
                 "-o", "ServerAliveInterval=15", "-MN", "-S", control.replace('%', '%%'), "-p",
                 str(self.networkservice.port), "-l", self.networkservice.username,
                 self.networkservice.address]

        # proxy via the exporter if we have an ifname suffix
        address = self.networkservice.address
        if address.count('%') > 1:
            raise ValueError(f"Multiple '%' found in '{address}'.")
        if '%' in address:
            address, ifname = address.split('%', 1)
        else:
            ifname = None

        proxy_cmd = proxymanager.get_command(self.networkservice, address, self.networkservice.port, ifname)
        if proxy_cmd:  # only proxy if needed
            args += [
                "-o", f"ProxyCommand={' '.join(proxy_cmd)} 2>{self.tmpdir}/proxy-stderr"
            ]

        env = os.environ.copy()
        pass_file = ''
        if self.networkservice.password:
            fd, pass_file = tempfile.mkstemp()
            os.fchmod(fd, stat.S_IRWXU)
            #with openssh>=8.4 SSH_ASKPASS_REQUIRE can be used to force SSH_ASK_PASS
            #openssh<8.4 requires the DISPLAY var and a detached process with start_new_session=True
            env = {'SSH_ASKPASS': pass_file, 'DISPLAY':'', 'SSH_ASKPASS_REQUIRE':'force'}
            with open(fd, 'w') as f:
                f.write("#!/bin/sh\necho " + self.networkservice.password)

        self.process = subprocess.Popen(args, env=env,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL,
                                        start_new_session=True)

        try:
            subprocess_timeout = timeout + 5
            return_value = self.process.wait(timeout=subprocess_timeout)
            if return_value != 0:
                stdout = self.process.stdout.readlines()
                for line in stdout:
                    self.logger.warning("ssh: %s", line.rstrip().decode(encoding="utf-8", errors="replace"))

                try:
                    proxy_error = open(self.tmpdir+'/proxy-stderr').read().strip()
                    if proxy_error:
                        raise ExecutionError(
                            f"Failed to connect to {self.networkservice.address} with {' '.join(args)}: error from SSH ProxyCommand: {proxy_error}",  # pylint: disable=line-too-long
                            stdout=stdout,
                        )
                except FileNotFoundError:
                    pass

                raise ExecutionError(
                    f"Failed to connect to {self.networkservice.address} with {' '.join(args)}: return code {return_value}",  # pylint: disable=line-too-long
                    stdout=stdout,
                )
        except subprocess.TimeoutExpired:
            raise ExecutionError(
                f"Subprocess timed out [{subprocess_timeout}s] while executing {args}",
            )
        finally:
            if self.networkservice.password and os.path.exists(pass_file):
                os.remove(pass_file)

        if not os.path.exists(control):
            raise ExecutionError(
                f"no control socket to {self.networkservice.address}"
            )

        self.logger.info('Connected to %s', self.networkservice.address)

        return control

    @Driver.check_active
    @step(args=['cmd'], result=True)
    def run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=None): # pylint: disable=unused-argument
        return self._run(cmd, codec=codec, decodeerrors=decodeerrors)

    def _run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=None): # pylint: disable=unused-argument
        """Execute `cmd` on the target.

        This method runs the specified `cmd` as a command on its target.
        It uses the ssh shell command to run the command and parses the exitcode.
        cmd - command to be run on the target

        returns:
        (stdout, stderr, returncode)
        """
        if not self._check_keepalive():
            raise ExecutionError("Keepalive no longer running")

        complete_cmd = ["ssh", "-x", *self.ssh_prefix,
                        "-p", str(self.networkservice.port), "-l", self.networkservice.username,
                        self.networkservice.address
                        ] + cmd.split(" ")
        self.logger.debug("Sending command: %s", complete_cmd)
        if self.stderr_merge:
            stderr_pipe = subprocess.STDOUT
        else:
            stderr_pipe = subprocess.PIPE
        try:
            sub = subprocess.Popen(
                complete_cmd, stdout=subprocess.PIPE, stderr=stderr_pipe
            )
        except:
            raise ExecutionError(
                f"error executing command: {complete_cmd}"
            )

        stdout, stderr = sub.communicate(timeout=timeout)
        stdout = stdout.decode(codec, decodeerrors).split('\n')
        if stdout[-1] == '':
            stdout.pop()
        if stderr is None:
            stderr = []
        else:
            stderr = stderr.decode(codec, decodeerrors).split('\n')
            stderr.pop()
        return (stdout, stderr, sub.returncode)

    def interact(self, cmd=None):
        assert cmd is None or isinstance(cmd, list)

        if not self._check_keepalive():
            raise ExecutionError("Keepalive no longer running")

        complete_cmd = ["ssh", "-x", *self.ssh_prefix,
                        "-t",
                        self.networkservice.address
                        ]
        if cmd:
            complete_cmd += ["--", *cmd]
        self.logger.debug("Running command: %s", complete_cmd)
        sub = subprocess.Popen(
            complete_cmd,
        )
        return sub.wait()

    @contextlib.contextmanager
    def _forward(self, forward):
        cmd = ["ssh", *self.ssh_prefix,
               "-O", "forward", forward,
               self.networkservice.address
               ]
        self.logger.debug("Running command: %s", cmd)
        subprocess.run(cmd, check=True)
        try:
            yield
        finally:
            cmd = ["ssh", *self.ssh_prefix,
                   "-O", "cancel", forward,
                   self.networkservice.address
                   ]
            self.logger.debug("Running command: %s", cmd)
            # Master socket may have been cleaned up already, so don't bother
            # the user with an error message
            subprocess.run(cmd, stderr=subprocess.DEVNULL)

    @Driver.check_active
    @contextlib.contextmanager
    def forward_local_port(self, remoteport, localport=None):
        """Forward a local port to a remote port on the target

        A context manager that keeps a local port forwarded to a remote port as
        long as the context remains valid. A connection can be made to the
        returned port on localhost and it will be forwarded to the remote port
        on the target device

        usage:
            with ssh.forward_local_port(8080) as localport:
                # Use localhost:localport here to connect to port 8080 on the
                # target

        returns:
        localport
        """
        if not self._check_keepalive():
            raise ExecutionError("Keepalive no longer running")

        if localport is None:
            localport = get_free_port()

        forward = f"-L{localport:d}:localhost:{remoteport:d}"
        with self._forward(forward):
            yield localport

    @Driver.check_active
    @contextlib.contextmanager
    def forward_remote_port(self, remoteport, localport):
        """Forward a remote port on the target to a local port

        A context manager that keeps a remote port forwarded to a local port as
        long as the context remains valid. A connection can be made to the
        remote on the target device will be forwarded to the returned local
        port on localhost

        usage:
            with ssh.forward_remote_port(8080, 8081) as localport:
                # Connections to port 8080 on the target will be redirected to
                # localhost:8081
        """
        if not self._check_keepalive():
            raise ExecutionError("Keepalive no longer running")

        forward = f"-R{remoteport:d}:localhost:{localport:d}"
        with self._forward(forward):
            yield

    @Driver.check_active
    @step(args=['src', 'dst'])
    def scp(self, *, src, dst):
        if not self._check_keepalive():
            raise ExecutionError("Keepalive no longer running")

        if src.startswith(':') == dst.startswith(':'):
            raise ValueError("Either source or destination must be remote (start with :)")
        if src.startswith(':'):
            src = '_' + src
        if dst.startswith(':'):
            dst = '_' + dst

        complete_cmd = ["scp",
                "-F", "none",
                "-o", f"ControlPath={self.control.replace('%', '%%')}",
                src, dst,
        ]
        self.logger.info("Running command: %s", complete_cmd)
        sub = subprocess.Popen(
            complete_cmd,
        )
        return sub.wait()

    @Driver.check_active
    @step(args=['src', 'dst', 'extra'])
    def rsync(self, *, src, dst, extra=[]):
        if not self._check_keepalive():
            raise ExecutionError("Keepalive no longer running")

        if src.startswith(':') == dst.startswith(':'):
            raise ValueError("Either source or destination must be remote (start with :)")
        if src.startswith(':'):
            src = '_' + src
        if dst.startswith(':'):
            dst = '_' + dst

        ssh_cmd = ["ssh",
                "-F", "none",
                "-o", f"ControlPath={self.control.replace('%', '%%')}",
        ]

        complete_cmd = ["rsync",
                "-v",
                f"--rsh={' '.join(ssh_cmd)}",
                "-rlpt",  # --recursive --links --perms --times
                "--one-file-system",
                "--progress",
                *extra,
                src, dst,
        ]
        self.logger.info("Running command: %s", complete_cmd)
        sub = subprocess.Popen(
            complete_cmd,
        )
        return sub.wait()

    @Driver.check_active
    @step(args=['path', 'mountpoint'])
    def sshfs(self, *, path, mountpoint):
        if not self._check_keepalive():
            raise ExecutionError("Keepalive no longer running")

        complete_cmd = ["sshfs",
                "-F", "none",
                "-f",
                "-o", f"ControlPath={self.control.replace('%', '%%')}",
                f":{path}",
                mountpoint,
        ]

        self.logger.debug("Running command: %s", complete_cmd)
        sub = subprocess.Popen(
            complete_cmd,
        )
        try:
            sub.wait(1)
            raise ExecutionError(
                f"error executing command: {complete_cmd}"
            )
        except subprocess.TimeoutExpired:  # still running
            self.logger.info("Started SSHFS on %s. Press CTRL-C to stop.", mountpoint)

        sub.wait()

    def get_status(self):
        """The SSHDriver is always connected, return 1"""
        return 1

    @Driver.check_active
    @step(args=['filename', 'remotepath'])
    def put(self, filename, remotepath=''):
        transfer_cmd = [
            "scp",
            *self.ssh_prefix,
            "-P", str(self.networkservice.port),
            "-r",
            filename,
            f"{self.networkservice.username}@{self.networkservice.address}:{remotepath}"
            ]

        try:
            sub = subprocess.call(
                transfer_cmd
            )  #, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise ExecutionError(
                f"error executing command: {transfer_cmd}"
            )
        if sub != 0:
            raise ExecutionError(
                f"error executing command: {transfer_cmd}"
            )

    @Driver.check_active
    @step(args=['filename', 'destination'])
    def get(self, filename, destination="."):
        transfer_cmd = [
            "scp",
            *self.ssh_prefix,
            "-P", str(self.networkservice.port),
            "-r",
            f"{self.networkservice.username}@{self.networkservice.address}:{filename}",
            destination
            ]

        try:
            sub = subprocess.call(
                transfer_cmd
            )  #, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise ExecutionError(
                f"error executing command: {transfer_cmd}"
            )
        if sub != 0:
            raise ExecutionError(
                f"error executing command: {transfer_cmd}"
            )

    def _cleanup_own_master(self):
        """Exit the controlmaster and delete the tmpdir"""
        complete_cmd = f"ssh -x -o ControlPath={self.control} -O exit -p {self.networkservice.port} -l {self.networkservice.username} {self.networkservice.address}".split(' ')  # pylint: disable=line-too-long
        res = subprocess.call(
            complete_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if res != 0:
            self.logger.info("Socket already closed")
        shutil.rmtree(self.tmpdir)

    def _start_keepalive(self):
        """Starts a keepalive connection via the own or external master."""
        args = ["ssh", *self.ssh_prefix, self.networkservice.address, "cat"]

        assert self._keepalive is None
        self._keepalive = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.logger.debug('Started keepalive for %s', self.networkservice.address)

    def _check_keepalive(self):
        return self._keepalive.poll() is None

    def _stop_keepalive(self):
        assert self._keepalive is not None

        self.logger.debug('Stopping keepalive for %s', self.networkservice.address)

        try:
            self._keepalive.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            self._keepalive.kill()

        try:
            self._keepalive.wait(timeout=60)
        finally:
            self._keepalive = None
