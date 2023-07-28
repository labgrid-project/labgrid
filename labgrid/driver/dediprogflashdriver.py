import os.path
import attr

from ..resource import NetworkDediprogFlasher
from ..factory import target_factory
from ..step import step
from .common import Driver, check_file
from ..util.managedfile import ManagedFile
from ..util.helper import processwrapper


@target_factory.reg_driver
@attr.s(eq=False)
class DediprogFlashDriver(Driver):
    """ The DediprogFlashDriver uses the dediprog utility to write an image
    to a raw rom. The driver is a pure wrapper of the dpcmd utility"""
    bindings = {
        'flasher': {"DediprogFlasher", NetworkDediprogFlasher},
    }

    image = attr.ib(validator=attr.validators.optional(attr.validators.instance_of(str)),
                    default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('dpcmd')
        else:
            self.tool = 'dpcmd'

    def _get_dediprog_prefix(self):
        return self.flasher.command_prefix + [self.tool]

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    def map_vcc(self):
        vcc_map = {'3.5V': '0', '2.5V': '1', '1.8V': '2'}
        return vcc_map[self.flasher.vcc]

    @Driver.check_active
    @step(title='call', args=['args'])
    def __call__(self, *args):
        vcc = self.map_vcc()
        arg_list = list(args)
        arg_list.append('--vcc')
        arg_list.append(vcc)
        arg_list.append('--silent')
        processwrapper.check_output(self._get_dediprog_prefix() + arg_list)

    @Driver.check_active
    @step(args=['filename'])
    def flash(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        filename = os.path.abspath(filename)
        check_file(filename)
        mf = ManagedFile(filename, self.flasher)
        mf.sync_to_resource()

        self('--auto', mf.get_remote_path(), '--verify', '-x', 'ff')

    @Driver.check_active
    def erase(self):
        self('--erase')
