"""The USBStick module provides support to interactively use a simulated USB
device in a test."""
import enum
import os

import attr

from ..exceptions import NoDriverFoundError
from ..protocol import CommandProtocol, FileTransferProtocol
from ..step import step


class USBStatus(enum.Enum):
    """This class describes the USBStick Status"""
    unplugged = 0
    plugged = 1
    mounted = 2


@attr.s(cmp=False)
class USBStick(object):
    """The USBStick class provides an easy to use interface to describe a
    target as an USB Stick."""
    target = attr.ib()
    image_dir = attr.ib(validator=attr.validators.instance_of(str))
    image_name = attr.ib(default="", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.command = self.target.get_active_driver( #pylint: disable=no-member
            CommandProtocol
        )
        self.fileservice = self.target.get_active_driver( #pylint: disable=no-member
            FileTransferProtocol
        )
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
        self.status = USBStatus.unplugged
        self._images = []
        if self.image_name:
            self._images.append(os.path.basename(self.image_name))

    @step()
    def plug_in(self):
        """Insert the USBStick

        This function plugs the virtual USB Stick in, making it available to
        the connected computer."""
        if not self.image_name:
            raise StateError("No Image selected, please upload and select an image")
        if self.status == USBStatus.unplugged:
            self.command.run_check(
                "modprobe g_mass_storage file={dir}{image}".format(
                    dir=self.image_dir, image=self.image_name
                )
            )
            self.status = USBStatus.plugged

    @step()
    def plug_out(self):
        """Plugs out the USBStick

        Plugs out the USBStick from the connected computer, does nothing if it is
        already unplugged"""
        if self.status == USBStatus.plugged:
            self.command.run_check("modprobe -r g_mass_storage")
            self.status = USBStatus.unplugged

    @step(args=['filename', 'destination'])
    def put_file(self, filename, destination=""):
        """Put a file onto the USBStick Image

        Puts a file onto the USB Stick, raises a StateError if it is not
        mounted on the host computer."""
        if not destination:
            destination = os.path.basename(filename)
        if self.status != USBStatus.unplugged:
            raise StateError("Device still plugged in, can't upload image")
        self.command.run_check(
            "losetup -Pf {}/{}".format(self.image_dir, self.image_name)
        )
        self.command.run_check("mount /dev/loop0p1 /mnt/")
        self.fileservice.put(
            filename,
            "/mnt/{dest}".format(
                dest=destination
            )
        )
        self.command.run_check("umount /mnt/")
        self.command.run_check("losetup -D")

    @step(args=['filename'])
    def get_file(self, filename):
        """Gets a file from the USBStick Image

        Gets a file from the USB Stick, raises a StateError if it is not
        mounted on the host computer."""
        if self.status != USBStatus.unplugged:
            raise StateError("Device still plugged in, can't upload image")
        self.command.run_check(
            "losetup -Pf {}/{}".format(self.image_dir, self.image_name)
        )
        self.command.run_check("mount /dev/loop0p1 /mnt/")
        self.fileservice.get(
            "/mnt/{filename}".format(
                filename=filename
            )
        )
        self.command.run_check("umount /mnt/")
        self.command.run_check("losetup -D")

    @step(args=['image'])
    def upload_image(self, image):
        """Upload a complete image as a new USB Stick

        This replaces the current USB Stick image, storing it permanently on
        the RiotBoard."""
        if self.status != USBStatus.unplugged:
            raise StateError("Device still plugged in, can't insert new image")
        self.fileservice.put(image, self.image_dir)
        self._images.append(os.path.basename(image))

    @step(args=['image_name'])
    def switch_image(self, image_name):
        """Switch between already uploaded images on the target."""
        if self.status != USBStatus.unplugged:
            raise StateError("Device still plugged in, can't switch to different image")
        if image_name not in self._images:
            raise StateError("No such Image available")
        self.command.run("umount /mnt/")
        self.command.run("losetup -D")
        self.image_name = image_name


@attr.s(cmp=False)
class StateError(Exception):
    """Exception which indicates a error in the state handling of the test"""
    msg = attr.ib()
