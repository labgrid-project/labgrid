# pylint: disable=no-member
import os.path
import attr

from ..factory import target_factory
from ..step import step
from .common import Driver
from ..util.managedfile import ManagedFile



@attr.s(eq=False)
class BaseProviderDriver(Driver):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step(args=['filename'], result=True)
    def stage(self, filename):
        symlink = os.path.join(self.provider.internal, os.path.basename(filename))
        assert symlink.startswith(self.provider.internal)

        mf = ManagedFile(filename, self.provider)
        mf.sync_to_resource(symlink=symlink)

        return self.provider.external + symlink[len(self.provider.internal):]


@target_factory.reg_driver
@attr.s(eq=False)
class TFTPProviderDriver(BaseProviderDriver):
    bindings = {
        "provider": {"TFTPProvider", "RemoteTFTPProvider"},
    }


@target_factory.reg_driver
@attr.s(eq=False)
class NFSPProviderDriver(BaseProviderDriver):
    bindings = {
        "provider": {"NFSProvider", "RemoteNFSProvider"},
    }


@target_factory.reg_driver
@attr.s(eq=False)
class HTTPProviderDriver(BaseProviderDriver):
    bindings = {
        "provider": {"HTTPProvider", "RemoteHTTPProvider"},
    }
