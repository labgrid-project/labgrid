"""The SSHDriver uses SSH as a transport to implement CommandProtocol and FileTransferProtocol"""
import contextlib
import os
import re
import stat
import shlex
import shutil
import subprocess
import tempfile
import time
from functools import cached_property

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
from ..util.ssh import get_ssh_connect_timeout


@target_factory.reg_driver
@attr.s(eq=False)
class SSHDriver(CommandMixin, Driver, CommandProtocol, FileTransferProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    bindings = {"networkservice": "NetworkService", }
    priorities = {CommandProtocol: 10, FileTransferProtocol: 10}
    keyfile = attr.ib(default="", validator=attr.validators.instance_of(str))
    stderr_merge = attr.ib(default=False, validator=attr.validators.instance_of(bool))
    connection_timeout = attr.ib(default=float(get_ssh_connect_timeout()), validator=attr.validators.instance_of(float))
    explicit_sftp_mode = attr.ib(default=False, validator=attr.validators.instance_of(bool))
    explicit_scp_mode = attr.ib(default=False, validator=attr.validators.instance_of(bool))
    username = attr.ib(default="", validator=attr.validators.instance_of(str))
    password = attr.ib(default="", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._keepalive = None
        self._ssh = self._get_tool("ssh")
        self._scp = self._get_tool("scp")
        self._sshfs = self._get_tool("sshfs")
        self._rsync = self._get_tool("rsync")

    def _get_tool(self, name):
        if self.target.env:
            return self.target.env.config.get_tool(name)
        return name

    def _get_username(self):
        """Get the username from this class or from NetworkService"""
        return self.username or self.networkservice.username

    def _get_password(self):
        """Get the password from this class or from NetworkService"""
        return self.password or self.networkservice.password

    def on_activate(self):
        self.ssh_prefix = ["-o", "LogLevel=ERROR"]
        if self.keyfile:
            keyfile_path = self.keyfile
            if self.target.env:
                keyfile_path = self.target.env.config.resolve_path(self.keyfile)
            self.ssh_prefix += ["-i", keyfile_path ]
        if not self._get_password():
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

    @property
    def skip_deactivate_on_export(self):
        # We need to keep the connection to the target open.
        return True

    def _start_own_master(self):
        """Starts a controlmaster connection in a temporary directory."""

        timeout = Timeout(self.connection_timeout)

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

        self.tmpdir = tempfile.mkdtemp(prefix='lg-ssh-')
        control = os.path.join(
            self.tmpdir, f'control-{self.networkservice.address}'
        )

        args = [self._ssh, "-f", *self.ssh_prefix, "-x", "-o", f"ConnectTimeout={timeout}",
                 "-o", "ControlPersist=300", "-o",
                 "UserKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=no",
                 "-o", "ServerAliveInterval=15", "-MN", "-S", control.replace('%', '%%'), "-p",
                 str(self.networkservice.port), "-l", self._get_username(),
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
        if self._get_password():
            fd, pass_file = tempfile.mkstemp()
            os.fchmod(fd, stat.S_IRWXU)
            #with openssh>=8.4 SSH_ASKPASS_REQUIRE can be used to force SSH_ASK_PASS
            #openssh<8.4 requires the DISPLAY var and a detached process with start_new_session=True
            env = {'SSH_ASKPASS': pass_file, 'DISPLAY':'', 'SSH_ASKPASS_REQUIRE':'force'}
            with open(fd, 'w') as f:
                f.write("#!/bin/sh\necho " + shlex.quote(self._get_password()))

        self.process = subprocess.Popen(args, env=env,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL,
                                        start_new_session=True)

        try:
            subprocess_timeout = timeout + 5
            return_value = self.process.wait(timeout=subprocess_timeout)
            if return_value != 0:
                stdout, _ = self.process.communicate(timeout=subprocess_timeout)
                stdout = stdout.split(b"\n")
                for line in stdout:
                    self.logger.warning("ssh: %s", line.rstrip().decode(encoding="utf-8", errors="replace"))

                try:
                    with open(f'{self.tmpdir}/proxy-stderr') as proxy_err_fd:
                        proxy_error = proxy_err_fd.read().strip()
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
            if self._get_password() and os.path.exists(pass_file):
                os.remove(pass_file)

        if not os.path.exists(control):
            raise ExecutionError(
                f"no control socket to {self.networkservice.address}"
            )

        self.logger.info('Connected to %s', self.networkservice.address)

        return control

    @Driver.check_active
    @step(args=['cmd'], result=True)
    def run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=None):
        return self._run(cmd, codec=codec, decodeerrors=decodeerrors, timeout=timeout)

    def _run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=None):
        """Execute `cmd` on the target.

        This method runs the specified `cmd` as a command on its target.
        It uses the ssh shell command to run the command and parses the exitcode.
        cmd - command to be run on the target

        returns:
        (stdout, stderr, returncode)
        """
        if not self._check_keepalive():
            raise ExecutionError("Keepalive no longer running")

        complete_cmd = [self._ssh, "-x", *self.ssh_prefix,
                        "-p", str(self.networkservice.port), "-l", self._get_username(),
                        self.networkservice.address
                        ] + cmd.split(" ")
        self.logger.debug("Sending command: %s", complete_cmd)
        if self.stderr_merge:
            stderr_pipe = subprocess.STDOUT
        else:
            stderr_pipe = subprocess.PIPE
        try:
            sub = subprocess.Popen(
                complete_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr_pipe
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

        complete_cmd = [self._ssh, "-x", *self.ssh_prefix,
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
        cmd = [self._ssh, *self.ssh_prefix,
               "-O", "forward", forward,
               self.networkservice.address
               ]
        self.logger.debug("Running command: %s", cmd)
        subprocess.run(cmd, check=True)
        try:
            yield
        finally:
            cmd = [self._ssh, *self.ssh_prefix,
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
    @contextlib.contextmanager
    def forward_unix_socket(self, unixsocket, localport=None):
        """Forward a unix socket on the target to a local port

        A context manager that keeps a unix socket forwarded to a local port as
        long as the context remains valid. A connection can be made to the
        remote socket on the target device will be forwarded to the returned
        local port on localhost

        usage:
            with ssh.forward_unix_socket("/run/docker.sock") as localport:
                # Use localhost:localport here to connect to the socket on the
                # target

        returns:
        localport
        """
        if not self._check_keepalive():
            raise ExecutionError("Keepalive no longer running")

        if localport is None:
            localport = get_free_port()

        forward = f"-L{localport:d}:{unixsocket:s}"
        with self._forward(forward):
            yield localport

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

        complete_cmd = [self._scp,
                "-S", self._ssh,
                "-F", "none",
                "-o", f"ControlPath={self.control.replace('%', '%%')}",
                src, dst,
        ]
        
        if self.explicit_sftp_mode and self._scp_supports_explicit_sftp_mode():
            complete_cmd.insert(1, "-s")
        if self.explicit_scp_mode and self._scp_supports_explicit_scp_mode():
            complete_cmd.insert(1, "-O")

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

        ssh_cmd = [self._ssh,
                "-F", "none",
                "-o", f"ControlPath={self.control.replace('%', '%%')}",
        ]

        complete_cmd = [self._rsync,
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

        complete_cmd = [self._sshfs,
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

    @cached_property
    def _ssh_version(self):
        version = subprocess.run([self._ssh, "-V"], capture_output=True, text=True)
        version = re.match(r"^OpenSSH_(\d+)\.(\d+)", version.stderr)
        return tuple(int(x) for x in version.groups())

    def _scp_supports_explicit_sftp_mode(self):
        major, minor = self._ssh_version

        # OpenSSH >= 8.6 supports explicitly using the SFTP protocol via -s
        if major == 8 and minor >= 6:
            return True
        # OpenSSH >= 9.0 default to the SFTP protocol
        if major >= 9:
            return False
        raise Exception(f"OpenSSH version {major}.{minor} does not support explicit SFTP mode")

    def _scp_supports_explicit_scp_mode(self):
        major, minor = self._ssh_version

        # OpenSSH >= 9.0 default to the SFTP protocol
        if major >= 9:
            return True
        raise Exception(f"OpenSSH version {major}.{minor} does not support explicit SCP mode")

    @Driver.check_active
    @step(args=['filename', 'remotepath'])
    def put(self, filename, remotepath=''):
        transfer_cmd = [
            self._scp,
            "-S", self._ssh,
            *self.ssh_prefix,
            "-P", str(self.networkservice.port),
            "-r",
            filename,
            f"{self._get_username()}@{self.networkservice.address}:{remotepath}"
            ]

        if self.explicit_sftp_mode and self._scp_supports_explicit_sftp_mode():
            transfer_cmd.insert(1, "-s")
        if self.explicit_scp_mode and self._scp_supports_explicit_scp_mode():
            transfer_cmd.insert(1, "-O")

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
            self._scp,
            "-S", self._ssh,
            *self.ssh_prefix,
            "-P", str(self.networkservice.port),
            "-r",
            f"{self._get_username()}@{self.networkservice.address}:{filename}",
            destination
            ]

        if self.explicit_sftp_mode and self._scp_supports_explicit_sftp_mode():
            transfer_cmd.insert(1, "-s")
        if self.explicit_scp_mode and self._scp_supports_explicit_scp_mode():
            transfer_cmd.insert(1, "-O")

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
        complete_cmd = f"{self._ssh} -x -o ControlPath={self.control.replace('%', '%%')} -O exit -p {self.networkservice.port} -l {self._get_username()} {self.networkservice.address}".split(' ')  # pylint: disable=line-too-long
        res = subprocess.call(
            complete_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if res != 0:
            self.logger.info("Socket already closed")

        self.process.communicate()

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _start_keepalive(self):
        """Starts a keepalive connection via the own or external master."""
        args = [self._ssh, *self.ssh_prefix, self.networkservice.address, "cat"]

        assert self._keepalive is None
        self._keepalive = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )

        self.logger.debug('Started keepalive for %s', self.networkservice.address)

    def _check_keepalive(self):
        return self._keepalive.poll() is None

    def _stop_keepalive(self):
        assert self._keepalive is not None

        self.logger.debug('Stopping keepalive for %s', self.networkservice.address)

        stdout = None
        try:
            stdout, _ = self._keepalive.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            self._keepalive.kill()
            try:
                # Try again to get output
                stdout, _ = self._keepalive.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                self.logger.warning("ssh keepalive for %s timed out during termination", self.networkservice.address)
        finally:
            self._keepalive = None

        if stdout:
            for line in stdout.splitlines():
                self.logger.warning("Keepalive %s: %s", self.networkservice.address, line)
