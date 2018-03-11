# pylint: disable=no-member
import tempfile
import logging
import subprocess
import os
from functools import wraps

import attr
from ..driver.exception import ExecutionError

from .ports import get_free_port

__all__ = ['SSHMANAGER', 'SSHConnection', 'ForwardError']


@attr.s
class SSHConnectionManager:
    _connections = attr.ib(
        default=attr.Factory(dict),
        validator=attr.validators.optional(attr.validators.instance_of(dict))
    )
    _tmpdir = attr.ib(
        default=attr.
        Factory(lambda: tempfile.mkdtemp(prefix='labgrid-ssh-manager-')),
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def __attrs_post_init__(self):
        self.logger = logging.getLogger("{}".format(self))

    def get(self, host: str):
        instance = self._connections.get(host)
        if instance is None:
            # pylint: disable=unsupported-assignment-operation
            self.logger.debug("Trying to start new control socket")
            # instance = self._start_control_socket(host)
            instance = SSHConnection(host)
            instance.connect()
            self._connections[host] = instance
        return instance

    def add_connection(self, connection):
        # pylint: disable=unsupported-assignment-operation
        assert isinstance(connection, SSHConnection)
        if connection.host not in self._connections:
            self._connections[connection.host] = connection

    def remove_connection(self, connection):
        # pylint: disable=unsupported-assignment-operation
        assert isinstance(connection, SSHConnection)
        if connection.isactive():
            raise ExecutionError("Can't remove active connection")
        self._connections[connection.host] = connection

    def open(self, host):
        con = self.get(host)
        return con

    def close(self, host):
        con = self.get(host)
        con.disconnect()
        self.remove_connection(con)

    def request_forward(self, host, port):
        con = self.get(host)
        return con.add_port_forward(port)

    def remove_forward(self, host, port):
        con = self.get(host)
        con.remove_port_forward(port)

    def put_file(self, host, local_file, dest_file):
        con = self.get(host)
        con.put_file(local_file, dest_file)

    def get_file(self, host, dest_file, local_file):
        con = self.get(host)
        con.get_file(dest_file, local_file)


def check_active(func):
    """Check if an SSHConnection is active as a decorator"""

    @wraps(func)
    def wrapper(cls, *_args, **_kwargs):
        if not cls.isactive():
            raise ExecutionError(
                "{} can not be called ({} is not active)".format(
                    func.__qualname__, cls
                )
            )
        return func(cls, *_args, **_kwargs)

    return wrapper


@attr.s
class SSHConnection:
    """SSHConnections are individual connections to hosts managed by a control
    socket. In addition to command execution this class also provides an
    interface to manage port forwardings. These are used in the remote
    infrastructure to tunnel multiple connections over one SSH link.

    A public identity infrastructure is assumed, no extra username or passwords
    are supported."""
    host = attr.ib(validator=attr.validators.instance_of(str))
    _active = attr.ib(
        default=False, validator=attr.validators.instance_of(bool)
    )
    _tmpdir = attr.ib(
        default=attr.
        Factory(lambda: tempfile.mkdtemp(prefix="labgrid-connection-")),
        validator=attr.validators.instance_of(str)
    )
    _forwards = attr.ib(default=attr.Factory(dict))

    def __attrs_post_init__(self):
        self._logger = logging.getLogger("{}".format(self))
        self._ssh_prefix = "-o LogLevel=ERROR"
        self._ssh_prefix = "-o PasswordAuthentication=no"
        self._socket = os.path.join(
            self._tmpdir, 'control-{}'.format(self.host)
        )

    def _open_connection(self):
        """Internal function which appends the control socket and checks if the
        connection is already open"""
        self._ssh_prefix += " -o ControlPath={}".format(
            self._socket
        ) if self._check_master() else ""

    def _run_socket_command(self, command, forward=""):
        "Internal function to send a command to the control socket"
        complete_cmd = "ssh -x -o ControlPath={cpath} -O {command}{forward} {host}".format(
            cpath=self._socket,
            command=command,
            forward=forward,
            host=self.host
        ).split(' ')
        res = subprocess.check_call(
            complete_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )

        return res

    def _run_command(self, command):
        "Internal function to run a command over the SSH connection"
        complete_cmd = "ssh -x -o ControlPath={cpath} {host} {command}".format(
            cpath=self._socket,
            host=self.host,
            command=command,
        ).split(' ')
        res = subprocess.check_call(
            complete_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return res

    @check_active
    def run_command(self, command):
        """Run a command over the SSHConnection

        Args:
            command (string): The command to run

        Returns:
            int: exitcode of the command
        """
        return self._run_command(command)

    @check_active
    def get_file(self, remote_file, local_file):
        """Get a file from the remote host"""
        subprocess.check_call([
            "scp", "-o", "ControlPath={}".format(self._socket),
            "{}:{}".format(self.host, remote_file), "{}".format(local_file)
        ])

    @check_active
    def put_file(self, local_file, remote_path):
        """Put a file onto the remote host"""
        subprocess.check_call([
            "scp", "-o", "ControlPath={}".format(self._socket),
            "{}".format(local_file), "{}:{}".format(self.host, remote_path)
        ])

    @check_active
    def add_port_forward(self, remote_port):
        """forward command"""
        local_port = get_free_port()

        # pylint: disable=not-an-iterable
        if remote_port in self._forwards:
            return self._forwards[remote_port]
        self._run_socket_command(
            "forward", " -L {local}:localhost:{remote}".format(
                local=local_port, remote=remote_port
            )
        )
        self._forwards[remote_port] = local_port
        return local_port

    @check_active
    def remove_port_forward(self, remote_port):
        """cancel command"""
        local_port = self._forwards.pop(remote_port, None)

        # pylint: disable=not-an-iterable
        if local_port is None:
            raise ForwardError("Forward does not exist")

        self._run_socket_command(
            "cancel", " -L {local}:localhost:{remote}".format(
                local=local_port, remote=remote_port
            )
        )

    def connect(self):
        self._open_connection()
        self._active = True

    @check_active
    def disconnect(self):
        self._disconnect()

    def isactive(self):
        return self._active

    def _check_master(self):
        args = ["ssh", "-O", "check", "{}".format(self.host)]
        check = subprocess.call(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if check == 0:
            return ""

        return self._start_own_master()

    def _start_own_master(self):
        """Starts a controlmaster connection in a temporary directory."""
        control = os.path.join(self._tmpdir, 'control-{}'.format(self.host))
        args = (
            "ssh -n {} -x -o ConnectTimeout=30 -o ControlPersist=300 "
            "-o UserKnownHostsFile=/dev/null "
            "-o StrictHostKeyChecking=no -MN -S {} {}"
        ).format(self._ssh_prefix, control, self.host).split(" ")

        self.process = subprocess.Popen(
            args,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )

        try:
            if self.process.wait(timeout=30) is not 0:
                raise ExecutionError(
                    "failed to connect to {} with {} and {}".format(
                        self.host, args, self.process.wait()
                    )
                )
        except subprocess.TimeoutExpired:
            raise ExecutionError(
                "failed to connect to {} with {} and {}".format(
                    self.host, args, self.process.wait()
                )
            )

        if not os.path.exists(control):
            raise ExecutionError("no control socket to {}".format(self.host))

        self._logger.debug('Connected to %s', self.host)

        return control

    def _disconnect(self):
        self._run_socket_command("exit")
        self._active = False


SSHMANAGER = SSHConnectionManager()


@attr.s
class ForwardError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
