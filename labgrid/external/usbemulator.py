import subprocess
import attr
from ..resource import NetworkService
from ..protocol import CommandProtocol, FileTransferProtocol
from ..driver import NoDriverError

@attr.s
class USBStick(object):
    target = attr.ib()
    image_name  = attr.ib(validator=attr.validators.instance_of(str))
    status = attr.ib(default=1)

    _UNPLUGGED = 1
    _PLUGGED = 2

    def __post_attr_init__(self):
        self.command = self.target.get_driver(CommandProtocol) #pylint: disable=no-member
        if not self.command:
            raise NoDriverError("Target has no {} Driver".format(CommandProtocol))
        # self.fileservice = self.target.get_driver(FileTransferProtocol) #pylint: disable=no-member
        # if not self.fileservice:
        #     raise NoDriverError("Target has no {} Driver".format(FileTransferProtocol))
        self.ssh("mount /dev/mmcblk1p1 /mnt")

    def plug_in(self):
        self.ssh("modprobe g_mass_storage file=/mnt/{image}".format(image=self.image_name))

    def eject(self):
        self.ssh("modprobe -r g_mass_storage")

    def upload_file(self, filename):
        subprocess.call('scp {filname} {host}:/tmp/{filename}'.format(filename=filename).split(' '))

    def upload_image(self, image):
        if not self.status == USBStick._UNPLUGGED:
            raise StateError("Device stioll plugged in, can't insert new image")
        subprocess.call('scp {filname} {host}:/tmp/{image}'.format(filename=image).split(' '))

    def ssh(self, cmd):
        try:
            self.command.run(cmd)
        except:
            raise ExecutionError('Call failed: {}'.format(cmd))

    def __del__(self):
        self.ssh("modprobe -r g_mass_storage")

class ExecutionError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return "ExecutioError({msg})".format(msg=self.msg)

class StateError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return "StatError({msg})".format(msg=self.msg)
