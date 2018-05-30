"""The usbstick2 module provides support to simulate an USB Stick
with configfs system """
import enum
import os

import attr

from ..exceptions import NoDriverFoundError
from ..protocol import CommandProtocol, FileTransferProtocol
from ..step import step

configfspath = '/tmp/configfs'

def run_if(shell, check, *args):
    if check:
        shell.run_check(*args)
    else:
        shell.run(*args)

class USBStatus(enum.Enum):
    """This class describes the USBStick Status"""
    unknown = 0
    unplugged = 1
    plugged = 2
    mounted = 3

@attr.s(cmp=False)
class USBStick2(object):
    """The USBStick2 class provides an easy to simulate an USB Stick."""
    target = attr.ib()

    usbctrl = attr.ib(default="ci_hdrc.0", validator=attr.validators.instance_of(str))
    usbvendor = attr.ib(default="0xabcd", validator=attr.validators.instance_of(str))
    usbproduct = attr.ib(default="0x1234", validator=attr.validators.instance_of(str))
    usbstring = attr.ib(default="0x409", validator=attr.validators.instance_of(str))

    serial = attr.ib(default="myserial", validator=attr.validators.instance_of(str))
    manufacturer = attr.ib(default="mymfg", validator=attr.validators.instance_of(str))
    product = attr.ib(default="myproduct", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.status = USBStatus.unknown
        self.command = self.target.get_active_driver( #pylint: disable=no-member
            CommandProtocol
        )
        if not self.command:
            raise NoDriverFoundError(
                "Target has no {} Driver".format(CommandProtocol)
            )

        self.plug_out()

        stdout, stderr, returncode = self.command.run('ls {mnt}'.format(mnt=configfspath))
        if returncode != 1:
            raise StateError("Cannot mount configfs")

        self.status = USBStatus.unplugged

    @step()
    def plug_in(self):
        """Insert the USBStick"""
        if self.status == USBStatus.unplugged:
            self.command.run('mkdir -p {mnt}'.format(mnt=configfspath))
            stdout, stderr, returncode = self.command.run('mount -t configfs none {mnt}'.format(mnt=configfspath))
            if ((returncode != 0) and (returncode != 255)):
                raise StateError("Cannot mount configfs")

            # load mass storage modules
            self.command.run('modprobe libcomposite')
            self.command.run_check('lsmod | grep -c libcomposite')
            self.command.run('modprobe usb_f_mass_storage')
            self.command.run_check('lsmod | grep -c usb_f_mass_storage')
            self.command.run_check('ls {mnt}/usb_gadget'.format(mnt=configfspath))
            # create virtual usb device
            self.command.run('mkdir {mnt}/usb_gadget/g1'.format(mnt=configfspath))
            self.command.run_check('echo {vendor} > {mnt}/usb_gadget/g1/idVendor'.format(vendor=self.usbvendor, mnt=configfspath))
            self.command.run_check('echo {prod} > {mnt}/usb_gadget/g1/idProduct'.format(prod=self.usbproduct, mnt=configfspath))
            # add strings info
            self.command.run_check('mkdir {mnt}/usb_gadget/g1/strings/{st}'.format(mnt=configfspath, st=self.usbstring))
            self.command.run_check('echo {serial} > {mnt}/usb_gadget/g1/strings/{st}/serialnumber'.format(serial=self.serial, mnt=configfspath, st=self.usbstring))
            self.command.run_check('echo {mfg} > {mnt}/usb_gadget/g1/strings/{st}/manufacturer'.format(mfg=self.manufacturer, mnt=configfspath, st=self.usbstring))
            self.command.run_check('echo {prod} > {mnt}/usb_gadget/g1/strings/{st}/product'.format(prod=self.product, mnt=configfspath, st=self.usbstring))
            # create config
            self.command.run_check('mkdir {mnt}/usb_gadget/g1/configs/c.1'.format(mnt=configfspath))
            # add mass storage function
            self.command.run_check('mkdir {mnt}/usb_gadget/g1/functions/mass_storage.0'.format(mnt=configfspath))
            # link function to config
            self.command.run_check('ln -s {mnt}/usb_gadget/g1/functions/mass_storage.0 {mnt}/usb_gadget/g1/configs/c.1/mass_storage.0'.format(mnt=configfspath))
            self.status = USBStatus.plugged

    @step()
    def mount(self, image_path):
        if self.status == USBStatus.unplugged:
            self.plug_in()

        if self.status == USBStatus.plugged:
            self.command.run_check('echo {} > {mnt}/usb_gadget/g1/functions/mass_storage.0/lun.0/file'.format(image_path, mnt=configfspath))
            self.command.run_check('echo {ctrl} > {mnt}/usb_gadget/g1/UDC'.format(ctrl=self.usbctrl, mnt=configfspath))
            self.status = USBStatus.mounted

    @step()
    def umount(self):
        """Plugs out the USBStick"""
        check = self.status != USBStatus.unknown
        if self.status == USBStatus.mounted or self.status == USBStatus.unknown:
            run_if(self.command, check, 'echo "" > {mnt}/usb_gadget/g1/UDC'.format(mnt=configfspath))
            run_if(self.command, check, 'echo "" > {mnt}/usb_gadget/g1/functions/mass_storage.0/lun.0/file'.format(mnt=configfspath))
            self.status = USBStatus.plugged

    @step()
    def plug_out(self):
        check = self.status != USBStatus.unknown
        if self.status == USBStatus.mounted or self.status == USBStatus.unknown:
            self.umount()

        if self.status == USBStatus.plugged or self.status == USBStatus.unknown:
            run_if(self.command, check, 'rm {mnt}/usb_gadget/g1/configs/c.1/mass_storage.0'.format(mnt=configfspath))
            run_if(self.command, check, 'rmdir {mnt}/usb_gadget/g1/configs/c.1'.format(mnt=configfspath))
            run_if(self.command, check, 'rmdir {mnt}/usb_gadget/g1/functions/mass_storage.0'.format(mnt=configfspath))
            run_if(self.command, check, 'rmdir {mnt}/usb_gadget/g1/strings/{st}'.format(mnt=configfspath, st=self.usbstring))
            run_if(self.command, check, 'rmdir {mnt}/usb_gadget/g1'.format(mnt=configfspath))
            run_if(self.command, check, 'rmmod usb_f_mass_storage libcomposite'.format(mnt=configfspath))
            run_if(self.command, check, 'umount {mnt}'.format(mnt=configfspath))
            run_if(self.command, check, 'rmmod configfs'.format(mnt=configfspath))
            run_if(self.command, check, 'rmdir {mnt}'.format(mnt=configfspath))

            _, _, returncode = self.command.run('ls {mnt}'.format(mnt=configfspath))
            if returncode != 1:
                raise StateError("Cannot umount configfs")

            self.status = USBStatus.unplugged

@attr.s(cmp=False)
class StateError(Exception):
    """Exception which indicates a error in the state handling of the test"""
    msg = attr.ib()
