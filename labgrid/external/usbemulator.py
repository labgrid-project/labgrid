"""The USBStick module provides support to interactively use a simulated USB
device in a test."""
import enum

import attr

from ..protocol import CommandProtocol, FileTransferProtocol
from ..exceptions import NoDriverFoundError


class USBStatus(enum.Enum):
    """This class describes the USB Status"""
    unplugged = 0
    plugged = 1
    mounted = 2


@attr.s
class USBStick(object):
    target = attr.ib()
    image_name = attr.ib(validator=attr.validators.instance_of(str))
    status = attr.ib(default=1)


    def __attrs_post_init__(self):
        self.command = self.target.get_driver( #pylint: disable=no-member
            CommandProtocol
        )
        self.fileservice = self.target.get_driver(FileTransferProtocol) #pylint: disable=no-member
        if not self.command:
            raise NoDriverFoundError(
                "Target has no {} Driver".format(CommandProtocol)
            )
        self.fileservice = self.target.get_driver( #pylint: disable=no-member
            FileTransferProtocol
        )  #pylint: disable=no-member
        if not self.fileservice:
            raise NoDriverFoundError(
                "Target has no {} Driver".format(FileTransferProtocol)
            )
        self.command.run_check("mount /dev/mmcblk1p1 /mnt")
        self.status = USBStatus.unplugged

    def plug_in(self):
        """Insert the USBStick

        This function plugs the virtual USB Stick in, making it available to
        the connected computer."""
        if self.status == USBStatus.unplugged:
            self.command.run_check(
                "modprobe g_mass_storage file=/mnt/{image}".
                format(image=self.image_name)
            )
            self.status = USBStatus.plugged

    def eject(self):
        """Eject the USBStick

        Ejects the USBStick from the connected computer, does nothing if it is
        already connected"""
        if self.status == USBStatus.plugged:
            self.command.run_check("modprobe -r g_mass_storage")
            self.status = USBStatus.unplugged

    def upload_file(self, filename, destination=""):
        """Upload a file onto the USBStick Image

        Uploads a file onto the USB Stick, raises a StateError if it is not
        mounted on the host computer."""
        if self.status != USBStatus.mounted:
            raise StateError("Device not mounted, can't upload file")
        self.fileservice.put(
            filename,
            "/media/usb/{dest}/{filename}".format(
                dest=destination, filename=filename
            )
        )

    def upload_image(self, image):
        """Upload a complete image as a new USB Stick

        This replaces the current USB Stick image, storing it permanently on
        the RiotBoard."""
        if self.status != USBStatus.unplugged:
            raise StateError("Device still plugged in, can't insert new image")
        self.fileservice.put(image, "/mnt/backing_store")

    def __del__(self):
        self.command.run_check("modprobe -r g_mass_storage")


@attr.s
class StateError(Exception):
    """Exception which indicates a error in the state handling of the test"""
    msg = attr.ib()
