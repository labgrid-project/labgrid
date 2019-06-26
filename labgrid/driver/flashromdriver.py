# pylint: disable=no-member
import subprocess
import os.path
import logging
import attr

from ..resource import Flashrom, NetworkFlashrom
from ..factory import target_factory
from ..step import step
from ..protocol import BootstrapProtocol
from .common import Driver, check_file
from ..util.managedfile import ManagedFile


@target_factory.reg_driver
@attr.s(cmp=False)
class FlashromDriver(Driver, BootstrapProtocol):
    """ The Flashrom driver used the flashrom utility to write an image to a raw rom.
    The driver is a pure wrapper of the flashrom utility"""
    bindings = {
        'flashrom_resource': {Flashrom, NetworkFlashrom},
    }

    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger('{}'.format(self))
        if self.target.env:
            self.tool = self.target.env.config.get_tool('flashrom')
        else:
            self.tool = 'flashrom'
        self.logger.debug('Tool {}'.format(self.tool))

    def _get_flashrom_prefix(self):
        return self.flashrom_resource.command_prefix+[
            self.tool
        ]

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(title='call', args=['args'])
    def __call__(self, *args):
        arg_list = list(args)
        arg_list.append('-p')
        arg_list.append('{}'.format(self.flashrom_resource.programmer))
        self.logger.debug('Call: {} with args: {}'.format(self.tool, arg_list))
        subprocess.check_call(self._get_flashrom_prefix() + arg_list)

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        filename = os.path.abspath(filename)
        check_file(filename)
        mf = ManagedFile(filename, self.flashrom_resource)
        mf.sync_to_resource()
        self.logger.debug('Local File {} synced to remote path {}'.format(filename,
                                                                          mf.get_remote_path()))
        self('-w', mf.get_remote_path())
