import hashlib
import os

import attr

from .helper import get_user
from .ssh import sshmanager
from ..resource.common import Resource, NetworkResource


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
        converter=lambda x: os.path.abspath(str(x))
    )
    resource = attr.ib(
        validator=attr.validators.instance_of(Resource),
    )

    def __attrs_post_init__(self):
        if not os.path.isfile(self.local_path):
            raise FileNotFoundError("Local file {} not found".format(self.local_path))

        username = get_user()
        hasher = hashlib.sha256()
        with open(self.local_path, 'rb') as f:
            for block in iter(lambda: f.read(1048576), b''):
                hasher.update(block)
        self.hash = hasher.hexdigest()
        self.rpath = "/tmp/labgrid-{user}/{hash}/".format(
            user=username, hash=self.hash
        )

    def sync_to_resource(self):
        """sync the file to the host specified in a resource

        Raises:
            ExecutionError: if the SSH connection/copy fails
        """
        if isinstance(self.resource, NetworkResource):
            host = self.resource.host
            conn = sshmanager.open(host)
            conn.run_check("mkdir -p {}".format(self.rpath))
            conn.put_file(
                self.local_path,
                "{}{}".format(self.rpath, os.path.basename(self.local_path))
            )

    def get_remote_path(self):
        """Retrieve the remote file path

        Returns:
            str: path to the file on the remote host
        """
        if isinstance(self.resource, NetworkResource):
            return "{}{}".format(self.rpath, os.path.basename(self.local_path))

        return self.local_path

    def get_hash(self):
        """Retrieve the hash of the file

        Returns:
            str: SHA256 hexdigest of the file
        """
        return self.hash
