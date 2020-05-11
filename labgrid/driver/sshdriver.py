# pylint: disable=no-member
"""The SSHDriver uses SSH as a transport to implement CommandProtocol and FileTransferProtocol"""
import logging
import os
import shutil
import subprocess
import tempfile

import attr

from ..factory import target_factory
from ..protocol import CommandProtocol, FileTransferProtocol
from .commandmixin import CommandMixin
from .common import Driver
from ..step import step
from .exception import ExecutionError
from ..util.proxy import proxymanager


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
        self.logger = logging.getLogger("{}({})".format(self, self.target))
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

        self.control = self._check_master()
        self.ssh_prefix += ["-F", "/dev/null"]
        if self.control:
            self.ssh_prefix += ["-o", "ControlPath={}".format(self.control.replace('%', '%%'))]

        self._keepalive = None
        self._start_keepalive();

    def on_deactivate(self):
        try:
            self._stop_keepalive()
        finally:
            self._cleanup_own_master()

    def _start_own_master(self):
        """Starts a controlmaster connection in a temporary directory."""

        timeout = 30

        self.tmpdir = tempfile.mkdtemp(prefix='labgrid-ssh-tmp-')
        control = os.path.join(
            self.tmpdir, 'control-{}'.format(self.networkservice.address)
        )
        # use sshpass if we have a password
        args = ["sshpass", "-e"] if self.networkservice.password else []

        args += ["ssh", "-f", *self.ssh_prefix, "-x", "-o", "ConnectTimeout={}".format(timeout),
                 "-o", "ControlPersist=300", "-o",
                 "UserKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=no",
                 "-o", "ServerAliveInterval=15", "-MN", "-S", control.replace('%', '%%'), "-p",
                 str(self.networkservice.port), "-l", self.networkservice.username,
                 self.networkservice.address]

        # proxy via the exporter if we have an ifname suffix
        address = self.networkservice.address
        if address.count('%') > 1:
            raise ValueError("Multiple '%' found in '{}'.".format(address))
        if '%' in address:
            address, ifname = address.split('%', 1)
        else:
            ifname = None

        proxy_cmd = proxymanager.get_command(self.networkservice, address, self.networkservice.port, ifname)
        if proxy_cmd:  # only proxy if needed
            args += [
                "-o", "ProxyCommand={} 2>{}".format(
                    ' '.join(proxy_cmd),
                    self.tmpdir+'/proxy-stderr',
                )
            ]

        env = os.environ.copy()
        if self.networkservice.password:
            env['SSHPASS'] = self.networkservice.password
        self.process = subprocess.Popen(args, env=env,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        stdin=subprocess.DEVNULL)

        try:
            subprocess_timeout = timeout + 5
            return_value = self.process.wait(timeout=subprocess_timeout)
            if return_value != 0:
                stdout = self.process.stdout.readlines()
                stderr = self.process.stderr.readlines()

                try:
                    proxy_error = open(self.tmpdir+'/proxy-stderr').read().strip()
                    if proxy_error:
                        raise ExecutionError(
                            "Failed to connect to {} with {}: error from SSH ProxyCommand: {}".
                            format(self.networkservice.address, args, proxy_error),
                            stdout=stdout,
                        )
                except FileNotFoundError:
                    pass

                raise ExecutionError(
                    "Failed to connect to {} with {}: return code {}".
                    format(self.networkservice.address, args, return_value),
                    stdout=stdout,
                    stderr=stderr
                )
        except subprocess.TimeoutExpired:
            raise ExecutionError(
                "Subprocess timed out [{}s] while executing {}".
                format(subprocess_timeout, args),
            )

        if not os.path.exists(control):
            raise ExecutionError(
                "no control socket to {}".format(self.networkservice.address)
            )

        self.logger.debug('Connected to %s', self.networkservice.address)

        return control

    def _check_master(self):
        args = [
            "ssh", "-O", "check", "-l", self.networkservice.username, self.networkservice.address
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
                "error executing command: {}".format(complete_cmd)
            )

        stdout, stderr = sub.communicate(timeout=timeout)
        stdout = stdout.decode(codec, decodeerrors).split('\n')
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
            filename,
            "{user}@{host}:{remotepath}".format(
                user=self.networkservice.username,
                host=self.networkservice.address,
                remotepath=remotepath)
            ]

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
        transfer_cmd = [
            "scp",
            *self.ssh_prefix,
            "-P", str(self.networkservice.port),
            "{user}@{host}:{filename}".format(
                user=self.networkservice.username,
                host=self.networkservice.address,
                filename=filename),
            destination
            ]

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
        complete_cmd = "ssh -x -o ControlPath={cpath} -O exit -p {port} -l {user} {host}".format(
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

    def _start_keepalive(self):
        """Starts a keepalive connection via the own or external master."""
        args = ["ssh", *self.ssh_prefix, "cat"]

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
