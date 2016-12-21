import enum

import subprocess

import attr

from ..protocol import CommandProtocol, FileTransferProtocol
from ..resource import NetworkService

class USBStatus(enum.Enum):
    """This class describes the USB Status"""
    unplugged = 0
    plugged = 1

@attr.s
class USBStick(object):
    target = attr.ib()
    image_name = attr.ib(validator=attr.validators.instance_of(str))
    status = attr.ib(default=1)


    def __attrs_post_init__(self):
        self.command = self.target.get_driver(
            CommandProtocol
        )  #pylint: disable=no-member
        if not self.command:
            raise NoDriverError(
                "Target has no {} Driver".format(CommandProtocol)
            )
        # self.fileservice = self.target.get_driver(FileTransferProtocol) #pylint: disable=no-member
        # if not self.fileservice:
        #     raise NoDriverError("Target has no {} Driver".format(FileTransferProtocol))
        self.ssh("mount /dev/mmcblk1p1 /mnt")
        self.status = USBStatus.unplugged

    def plug_in(self):
        self.ssh(
            "modprobe g_mass_storage file=/mnt/{image}".
            format(image=self.image_name)
        )
        self.status = USBStatus.plugged

    def eject(self):
        self.ssh("modprobe -r g_mass_storage")
        self.status = USBStatus.unplugged

    def upload_file(self, filename):
        subprocess.call(
            'scp {filname} {host}:/tmp/{filename}'.format(filename=filename)
            .split(' ')
        )

    def upload_image(self, image):
        if not self.status == USBStatus.unplugged:
            raise StateError(
                "Device still plugged in, can't insert new image"
            )
        subprocess.call(
            'scp {filname} {host}:/tmp/{image}'.format(filename=image)
            .split(' ')
        )

    def ssh(self, cmd):
        try:
            self.command.run_check(cmd)
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
