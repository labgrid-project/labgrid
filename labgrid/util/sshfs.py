import logging
import os
import subprocess
import random
import string
import time
import shlex
from contextlib import contextmanager

import attr

from .ssh import sshmanager
from .timeout import Timeout
from ..driver.exception import ExecutionError
from ..resource.common import Resource, NetworkResource


DEFAULT_SFTP_SERVER = "podman run --rm -i --mount type=bind,source={path},target={path} labgrid/sftp-server:latest usr/lib/ssh/sftp-server -e {readonly}"
DEFAULT_RO_OPT = "-R"


@attr.s
class SSHFsExport:
    """
    Exports a local directory to a remote device using "reverse" SSH FS
    """

    local_path = attr.ib(
        validator=attr.validators.instance_of(str),
        converter=lambda x: os.path.abspath(str(x)),
    )
    resource = attr.ib(
        validator=attr.validators.instance_of(Resource),
    )
    readonly = attr.ib(
        default=True,
        validator=attr.validators.instance_of(bool),
    )

    def __attrs_post_init__(self):
        if not os.path.isdir(self.local_path):
            raise FileNotFoundError(f"Local directory {self.local_path} not found")
        self.logger = logging.getLogger(f"{self}")

    @contextmanager
    def export(self, remote_path=None):
        host = self.resource.host
        conn = sshmanager.open(host)

        # If no remote path was specified, mount on a temporary directory
        if remote_path is None:
            tmpname = "".join(random.choices(string.ascii_lowercase, k=10))
            remote_path = f"/tmp/labgrid-sshfs/{tmpname}/"
            conn.run_check(f"mkdir -p {remote_path}")

        env = self.resource.target.env

        if env is None:
            sftp_server_opt = DEFAULT_SFTP_SERVER
            ro_opt = DEFAULT_RO_OPT
        else:
            sftp_server_opt = env.config.get_option("sftp_server", DEFAULT_SFTP_SERVER)
            ro_opt = env.config.get_option("sftp_server_readonly_opt", DEFAULT_RO_OPT)

        sftp_command = shlex.split(
            sftp_server_opt.format(
                path=self.local_path,
                uid=str(os.getuid()),
                gid=str(os.getgid()),
                readonly=ro_opt if self.readonly else "",
            )
        )

        sshfs_command = conn.get_prefix() + [
            "sshfs",
            "-o",
            "slave",
            "-o",
            "idmap=user",
            f":{self.local_path}",
            remote_path,
        ]

        self.logger.info(
            "Running %s <-> %s", " ".join(sftp_command), " ".join(sshfs_command)
        )

        # Reverse sshfs requires that sftp-server running locally and sshfs
        # running remotely each have their stdout connected to the others
        # stdin. Connecting sftp-server stdout to sshfs stdin is done using
        # Popen pipes, but in order to connect sshfs stdout to sftp-stdin, an
        # external pipe is needed.
        (rfd, wfd) = os.pipe2(os.O_CLOEXEC)
        try:
            with subprocess.Popen(
                sftp_command,
                stdout=subprocess.PIPE,
                stdin=rfd,
            ) as sftp_server, subprocess.Popen(
                sshfs_command,
                stdout=wfd,
                stdin=sftp_server.stdout,
            ) as sshfs:
                # Close all file descriptor open in this process. This way, if
                # either process exits, the other will get the EPIPE error and
                # exit also. If this process doesn't close its copy of the
                # descriptors, that won't happen
                sftp_server.stdout.close()

                os.close(rfd)
                rfd = -1

                os.close(wfd)
                wfd = -1

                # Wait until the mount point appears remotely
                t = Timeout(30.0)

                while not t.expired:
                    (_, _, exitcode) = conn.run(f"mountpoint --quiet {remote_path}")

                    if exitcode == 0:
                        break

                    if sshfs.poll() is not None:
                        raise ExecutionError(
                            "sshfs process exited with {sshfs.returncode}"
                        )

                    if sftp_server.poll() is not None:
                        raise ExecutionError(
                            "sftp process exited with {sftp_server.returncode}"
                        )

                    time.sleep(1)

                if t.expired:
                    raise TimeoutError("Timeout waiting for SSH fs to mount")

                try:
                    yield remote_path
                finally:
                    sshfs.terminate()
                    sftp_server.terminate()

        finally:
            # Cleanup if not done already
            if rfd >= 0:
                os.close(rfd)

            if wfd >= 0:
                os.close(wfd)
