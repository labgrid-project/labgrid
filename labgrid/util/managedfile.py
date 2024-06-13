import hashlib
import logging
import os
import subprocess
from importlib import import_module

import attr

from .helper import get_user
from .ssh import sshmanager
from ..resource.common import Resource, NetworkResource
from ..driver.exception import ExecutionError


class ManagedFileError(Exception):
    pass


@attr.s
class ManagedFile:
    """ The ManagedFile allows the synchronisation of a file to a remote host.
    It has to be created with the to be synced file and the target resource as
    argument:

    ::
        from labgrid.util.managedfile import ManagedFile

        ManagedFile("/tmp/examplefile", <your-resource>)

    Synchronisation is done with the sync_to_resource method.
    """
    local_path = attr.ib(
        validator=attr.validators.instance_of(str),
        converter=lambda x: os.path.realpath(str(x))
    )
    resource = attr.ib(
        validator=attr.validators.instance_of(Resource),
    )
    detect_nfs = attr.ib(default=True, validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self):
        if not os.path.isfile(self.local_path):
            raise FileNotFoundError(f"Local file {self.local_path} not found")
        self.logger = logging.getLogger(f"{self}")
        self.hash = None
        self.rpath = None
        self._on_nfs_cached = None

    def sync_to_resource(self, symlink=None):
        """sync the file to the host specified in a resource

        Raises:
            ExecutionError: if the SSH connection/copy fails
        """
        if isinstance(self.resource, NetworkResource):
            host = self.resource.host
            conn = sshmanager.open(host)

            if self._on_nfs(conn):
                self.logger.info("File %s is accessible on %s, skipping copy", self.local_path, host)
                self.rpath = os.path.dirname(self.local_path) + "/"
            else:
                self.rpath = f"{self.get_user_cache_path()}/{self.get_hash()}/"
                self.logger.info("Synchronizing %s to %s", self.local_path, host)
                conn.run_check(f"mkdir -p {self.rpath}")
                conn.put_file(
                    self.local_path,
                    f"{self.rpath}{os.path.basename(self.local_path)}"
                )

            if symlink is not None:
                self.logger.info("Linking")
                try:
                    conn.run_check(f"test ! -e {symlink} -o -L {symlink}")
                except ExecutionError:
                    raise ManagedFileError(f"Path {symlink} exists but is not a symlink.")
                # use short options to be compatible with busybox
                # --symbolic --force --no-dereference
                conn.run_check(f"ln -sfn {self.rpath}{os.path.basename(self.local_path)} {symlink}")


    def _on_nfs(self, conn):
        if self._on_nfs_cached is not None:
            return self._on_nfs_cached

        if not self.detect_nfs:
            return False

        self._on_nfs_cached = False

        fmt = "inode=%i,size=%s,modified=%Y"
        # The stat command is very different on MacOs
        platform = import_module('platform')
        if platform.system() == 'Darwin':
            darwin_fmt = "inode=%i,size=%z,modified=%m"
            local = subprocess.run(["stat", "-f", darwin_fmt, self.local_path],
                                   stdout=subprocess.PIPE)
        else:
            local = subprocess.run(["stat", "--format", fmt, self.local_path],
                                   stdout=subprocess.PIPE)

        if local.returncode != 0:
            self.logger.debug("local: stat: unsuccessful error code %d", local.returncode)
            return False

        remote = conn.run(f"stat --format '{fmt}' {self.local_path}",
                          decodeerrors="backslashreplace")
        if remote[2] != 0:
            self.logger.debug("remote: stat: unsuccessful error code %d", remote[2])
            return False

        localout = local.stdout.decode("utf-8", "backslashreplace").split('\n')
        localout.pop() # remove trailing empty element

        if remote[0] != localout:
            self.logger.debug("state: local (%s) and remote (%s) output don't match",
                              remote[0], localout)
            return False

        self.rpath = os.path.dirname(self.local_path) + "/"
        self._on_nfs_cached = True

        return True

    def get_remote_path(self):
        """Retrieve the remote file path

        Returns:
            str: path to the file on the remote host
        """
        if isinstance(self.resource, NetworkResource):
            return f"{self.rpath}{os.path.basename(self.local_path)}"

        return self.local_path

    def get_hash(self):
        """Retrieve the hash of the file

        Returns:
            str: SHA256 hexdigest of the file
        """

        if self.hash is not None:
            return self.hash

        hasher = hashlib.sha256()
        with open(self.local_path, 'rb') as f:
            for block in iter(lambda: f.read(1048576), b''):
                hasher.update(block)
        self.hash = hasher.hexdigest()

        return self.hash

    def get_user_cache_path(self):
        return f"/var/cache/labgrid/{get_user()}"
