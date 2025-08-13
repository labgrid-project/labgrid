import atexit
import tempfile
import logging
import shutil
import subprocess
import os
from select import select
from functools import wraps
from typing import Dict

import attr
from ..driver.exception import ExecutionError

from .helper import get_free_port, processwrapper

__all__ = ['sshmanager', 'SSHConnection', 'ForwardError']

def get_ssh_connect_timeout():
    return int(os.environ.get("LG_SSH_CONNECT_TIMEOUT", 30))


@attr.s
class SSHConnectionManager:
    """The SSHConnectionManager manages multiple SSH connections. This class
    should not be directly instantiated, use the exported sshmanager from this
    module instead.
    """
    _connections: 'Dict[str, SSHConnection]' = attr.ib(
        default=attr.Factory(dict),
        init=False,
        validator=attr.validators.optional(attr.validators.instance_of(dict))
    )

    def __attrs_post_init__(self):
        self.logger = logging.getLogger(f"{self}")
        atexit.register(self.close_all)

    def get(self, host: str):
        """Retrieve or create a new connection to a given host

        Arguments:
            host (str): host to retrieve the connection for

        Returns:
            :obj:`SSHConnection`: the SSHConnection for the host"""
        instance = self._connections.get(host)
        if instance is None:
            self.logger.debug("Creating SSHConnection for %s", host)
            instance = SSHConnection(host)
            instance.connect()
            self._connections[host] = instance
        return instance

    def add_connection(self, connection):
        """Add an existing SSHConnection to the manager.
        This is useful for manually created connections which should also be
        available via the manager.

        Arguments:
            connection (:obj:`SSHConnection`): SSHconnection to add to the manager
        """
        assert isinstance(connection, SSHConnection)
        if connection.host not in self._connections:
            self._connections[connection.host] = connection

    def remove_connection(self, connection):
        assert isinstance(connection, SSHConnection)
        if connection.isconnected():
            raise ExecutionError("Can't remove connected connection")
        del self._connections[connection.host]

    def remove_by_name(self, name):
        del self._connections[name]

    def open(self, host):
        return self.get(host)

    def close(self, host):
        con = self.get(host)
        con.disconnect()
        self.remove_connection(con)

    def request_forward(self, host, dest, port):
        con = self.get(host)
        return con.add_port_forward(dest, port)

    def remove_forward(self, host, dest, port):
        con = self.get(host)
        con.remove_port_forward(dest, port)

    def put_file(self, host, local_file, remote_file):
        con = self.get(host)
        con.put_file(local_file, remote_file)

    def get_file(self, host, remote_file, local_file):
        con = self.get(host)
        con.get_file(remote_file, local_file)

    def close_all(self):
        """Close all open connections and remove them from the manager """
        for name, connection in self._connections.items():
            if connection.isconnected():
                connection.disconnect()
        names = self._connections.copy().keys()
        for name in names:
            self.remove_by_name(name)


def _check_connected(func):
    """Check if an SSHConnection is connected as a decorator"""

    @wraps(func)
    def wrapper(self, *_args, **_kwargs):
        if not self.isconnected():
            raise ExecutionError(
                f"{func.__qualname__} can not be called ({self} is not connected)"
            )
        return func(self, *_args, **_kwargs)

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
    _connected = attr.ib(
        default=False, init=False, validator=attr.validators.instance_of(bool)
    )
    _tmpdir = attr.ib(
        default=attr.Factory(lambda: tempfile.mkdtemp(prefix="lg-con-")),
        init=False,
        validator=attr.validators.instance_of(str)
    )
    _l_forwards = attr.ib(init=False, default=attr.Factory(dict))
    _r_forwards = attr.ib(init=False, default=attr.Factory(set))

    def __attrs_post_init__(self):
        self._logger = logging.getLogger(f"{self}")
        self._socket = None
        self._master = None
        self._keepalive = None
        atexit.register(self.cleanup)

    @staticmethod
    def _get_ssh_base_args():
        return ["-x", "-o", "LogLevel=ERROR", "-o", "PasswordAuthentication=no"]

    def _get_ssh_control_args(self):
        if self._socket:
            return [
                "-o", "ControlMaster=no",
                "-o", f"ControlPath={self._socket}",
            ]
        return []

    def _get_ssh_args(self):
        args = SSHConnection._get_ssh_base_args()
        args += self._get_ssh_control_args()
        return args

    def _open_connection(self):
        """Internal function which appends the control socket and checks if the
        connection is already open"""
        if self._check_external_master():
            self._logger.info("Using existing SSH connection to %s", self.host)
        else:
            self._start_own_master()
            self._logger.info("Created new SSH connection to %s", self.host)
        self._start_keepalive()
        self._connected = True

    def _run_socket_command(self, command, forward=None):
        "Internal function to send a command to the control socket"
        complete_cmd = ["ssh"] + self._get_ssh_args()
        complete_cmd += ["-O", command]
        if forward:
            for item in forward:
                complete_cmd.append(item)
        complete_cmd.append(self.host)
        self._logger.debug("Running control command: %s", " ".join(complete_cmd))
        subprocess.check_call(
            complete_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=2,
        )

    @_check_connected
    def get_prefix(self):
        return ["ssh"] + self._get_ssh_args() + [self.host]

    @_check_connected
    def run(self, command, *, codec="utf-8", decodeerrors="strict",
            force_tty=False, stderr_merge=False, stderr_loglevel=None,
            stdout_loglevel=None):

        """Run a command over the SSHConnection

        Args:
            command (string): The command to run
            codec (string, optional): output encoding. Defaults to "utf-8".
            decodeerrors (string, optional): behavior on decode errors. Defaults
                 to "strict". Refer to stdtypes' bytes.decode for details.
            force_tty (bool, optional): force allocate a tty (ssh -tt). Defaults
                 to False
            stderr_merge (bool, optional): merge ssh subprocess stderr into
                 stdout. Defaults to False.
            stdout_loglevel (int, optional): log stdout with specific log level
                 as well. Defaults to None, i.e. don't log.
            stderr_loglevel (int, optional): log stderr with specific log level
                 as well. Defaults to None, i.e. don't log.

        returns:
            (stdout, stderr, returncode)
        """

        complete_cmd = ["ssh"] + self._get_ssh_args()
        if force_tty:
            complete_cmd += ["-tt"]
        complete_cmd += [self.host, command]
        self._logger.debug("Sending command: %s", " ".join(complete_cmd))
        if stderr_merge:
            stderr_pipe = subprocess.STDOUT
        else:
            stderr_pipe = subprocess.PIPE
        try:
            sub = subprocess.Popen(
                complete_cmd, stdout=subprocess.PIPE, stderr=stderr_pipe,
                stdin=subprocess.DEVNULL
            )
        except:
            raise ExecutionError(
                f"error executing command: {complete_cmd}"
            )

        stdout = []
        stderr = []

        readable = {
            sub.stdout.fileno(): (sub.stdout, stdout, stdout_loglevel),
        }

        if sub.stderr is not None:
            readable[sub.stderr.fileno()] = (sub.stderr, stderr, stderr_loglevel)

        while readable:
            for fd in select(readable, [], [])[0]:
                stream, output, loglevel = readable[fd]
                line = stream.readline().decode(codec, decodeerrors)
                if line == "": # EOF
                    del readable[fd]
                else:
                    line = line.rstrip('\n')
                    output.append(line)
                    if loglevel is not None:
                        self._logger.log(loglevel, line)

        sub.communicate()
        return stdout, stderr, sub.returncode

    def run_check(self, command, *, codec="utf-8", decodeerrors="strict",
                  force_tty=False, stderr_merge=False, stderr_loglevel=None,
                  stdout_loglevel=None):
        """
        Runs a command over the SSHConnection
        returns the output if successful, raises ExecutionError otherwise.

        Except for the means of returning the value, this is equivalent to
        run.

        Args:
            command (string): The command to run
            codec (string, optional): output encoding. Defaults to "utf-8".
            decodeerrors (string, optional): behavior on decode errors. Defaults
                 to "strict". Refer to stdtypes' bytes.decode for details.
            force_tty (bool, optional): force allocate a tty (ssh -tt). Defaults
                 to False
            stderr_merge (bool, optional): merge ssh subprocess stderr into
                 stdout. Defaults to False.
            stdout_loglevel (int, optional): log stdout with specific log level
                 as well. Defaults to None, i.e. don't log.
            stderr_loglevel (int, optional): log stderr with specific log level
                 as well. Defaults to None, i.e. don't log.

        Returns:
            List[str]: stdout of the executed command if successful and
                       otherwise an ExecutionError Exception

        """
        stdout, stderr, exitcode = self.run(
            command, codec=codec, decodeerrors=decodeerrors, force_tty=force_tty,
            stderr_merge=stderr_merge, stdout_loglevel=stdout_loglevel,
            stderr_loglevel=stderr_loglevel
        )

        if exitcode != 0:
            raise ExecutionError(command, stdout, stderr)
        return stdout

    @_check_connected
    def get_file(self, remote_file, local_file):
        """Get a file from the remote host"""
        complete_cmd = ["scp"] + self._get_ssh_control_args()
        complete_cmd += [
            f"{self.host}:{remote_file}",
            f"{local_file}"
        ]
        self._logger.debug("Running command: %s", complete_cmd)
        subprocess.check_call(
            complete_cmd,
            stdin=subprocess.DEVNULL,
        )

    @_check_connected
    def put_file(self, local_file, remote_path):
        """Put a file onto the remote host"""
        complete_cmd = ["rsync", "--compress", "--sparse", "--copy-links", "--verbose", "--progress", "--times", "-e",
                        " ".join(['ssh'] + self._get_ssh_args())]
        complete_cmd += [
            f"{local_file}",
            f"{self.host}:{remote_path}"
        ]
        self._logger.debug("Running command: %s", complete_cmd)
        processwrapper.check_output(
            complete_cmd,
            stdin=subprocess.DEVNULL,
            print_on_silent_log=True
        )

    @_check_connected
    def add_port_forward(self, remote_host, remote_port, local_port=None):
        """forward command"""
        if local_port is None:
            local_port = get_free_port()
        destination = f"{remote_host}:{remote_port}"

        if destination in self._l_forwards:
            return self._l_forwards[destination]
        self._run_socket_command(
            "forward", [
                f"-L{local_port}:{destination}"
            ]
        )
        self._l_forwards[destination] = local_port
        return local_port

    @_check_connected
    def remove_port_forward(self, remote_host, remote_port):
        """cancel command"""
        destination = f"{remote_host}:{remote_port}"
        local_port = self._l_forwards.pop(destination, None)

        if local_port is None:
            raise ForwardError("Forward does not exist")

        self._run_socket_command(
            "cancel", [
                f"-L{local_port}:{destination}"
            ]
        )

    @_check_connected
    def add_remote_port_forward(self, remote_port, local_port, remote_bind=None):
        """remote forward command

        Note that the remote socket is not *bound* to any specific IP by
        default, making it reachable by the target. Also, 'GatewayPorts
        clientspecified' needs to be configured in the remote host's
        sshd_config.
        """
        if remote_bind is None:
            remote_bind = "*"

        forward = f"-R{remote_bind}:{remote_port:d}:localhost:{local_port:d}"

        self._run_socket_command("forward", [forward])
        self._r_forwards.add(forward)

    @_check_connected
    def remove_remote_port_forward(self, remote_port, local_port, remote_bind=None):
        """remote cancel command"""
        if remote_bind is None:
            remote_bind = "*"

        forward = f"-R{remote_bind}:{remote_port:d}:localhost:{local_port:d}"

        self._r_forwards.remove(forward)
        self._run_socket_command("cancel", [forward])

    def connect(self):
        if not self._connected:
            self._open_connection()

    def isconnected(self):
        return self._connected and self._check_keepalive()

    def _check_external_master(self):
        args = ["ssh", "-O", "check", f"{self.host}"]
        # We don't want to confuse the use with SSHs output here, so we need to
        # capture and parse it.
        proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        stdout, _ = proc.communicate(timeout=60)
        check = proc.wait()
        if check == 0:
            self._logger.debug("Found existing control socket")
            return True
        if b"No such file or directory" in stdout or b"No ControlPath specified" in stdout:
            self._logger.debug("No existing control socket found")
            return False

        self._logger.debug("Unexpected ssh check output '%s'", stdout)
        return False

    def _start_own_master(self):
        """Starts a controlmaster connection in a temporary directory."""
        control = os.path.join(self._tmpdir, f'control-{self.host}')

        connect_timeout = get_ssh_connect_timeout()

        self._logger.debug("ControlSocket: %s", control)
        args = ["ssh"] + SSHConnection._get_ssh_base_args()
        args += [
            "-n", "-MN",
            "-o", f"ConnectTimeout={connect_timeout}",
            "-o", "ControlPersist=300",
            "-o", "ControlMaster=yes",
            "-o", f"ControlPath={control}",
            # We don't want to ask the user to confirm host keys here.
            "-o", "StrictHostKeyChecking=yes",
            self.host,
        ]

        self._logger.debug("Master Start command: %s", " ".join(args))
        assert self._master is None
        self._master = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout, stderr = self._master.communicate(timeout=connect_timeout)
            if self._master.returncode != 0:
                raise ExecutionError(
                    f"failed to connect to {self.host} with args {args}, returncode={self._master.returncode} {stdout},{stderr}"  # pylint: disable=line-too-long
                )
        except subprocess.TimeoutExpired:
            self._master.kill()
            stdout, stderr = self._master.communicate()
            raise ExecutionError(
                f"failed to connect (timeout) to {self.host} with args {args}, process killed, got {stdout},{stderr}"  # pylint: disable=line-too-long
            )

        if not os.path.exists(control):
            raise ExecutionError(f"no control socket to {self.host}")

        self._socket = control

        self._logger.debug('Connected to %s', self.host)

    def _stop_own_master(self):
        assert self._socket is not None
        assert self._master is not None

        try:
            self._run_socket_command("cancel")
            self._run_socket_command("exit")
            # if the master doesn't terminate in less than 60 seconds,
            # something is very wrong
            self._master.communicate(timeout=60)
        finally:
            self._socket = None
            self._master = None

    def _start_keepalive(self):
        """Starts a keepalive connection via the own or external master."""
        args = ["ssh"] + self._get_ssh_args() + [self.host, "cat"]

        assert self._keepalive is None
        self._keepalive = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        self._logger.debug('Started keepalive for %s', self.host)

    def _check_keepalive(self):
        return self._keepalive.poll() is None

    def _stop_keepalive(self):
        assert self._keepalive is not None

        self._logger.debug('Stopping keepalive for %s', self.host)

        try:
            self._keepalive.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            self._keepalive.kill()
            self._keepalive.communicate(timeout=60)
        finally:
            self._keepalive = None

    @_check_connected
    def disconnect(self):
        assert self._connected
        try:
            self._stop_keepalive()

            if self._socket:
                self._logger.info("Closing SSH connection to %s", self.host)
                self._stop_own_master()
        finally:
            self._connected = False

    def cleanup(self):
        if self.isconnected():
            # cancel local forwards
            for destination, local_port in self._l_forwards.items():
                self._run_socket_command("cancel", [f"-L{local_port}:{destination}"])
            self._l_forwards.clear()
            # cancel remote forwards
            for forward in self._r_forwards:
                self._run_socket_command("cancel", [forward])
            self._r_forwards.clear()
            self.disconnect()
        shutil.rmtree(self._tmpdir)

sshmanager = SSHConnectionManager()

@attr.s
class ForwardError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
