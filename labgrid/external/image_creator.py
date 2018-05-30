"""The ImageCreator module provides support to create a raw image """
import enum
import os

import attr

from ..exceptions import NoDriverFoundError, NoResourceFoundError
from ..protocol import CommandProtocol
from ..step import step

class ICStatus(enum.Enum):
    """This class describes the ImageCreator Status"""
    unknown = 0
    initialized = 1
    created = 1

@attr.s(cmp=False)
class ImageCreator(object):
    """The ImageCreator class provides an easy to create a raw image """
    target = attr.ib()

    image_path = attr.ib(validator=attr.validators.instance_of(str))
    image_size = attr.ib(default=16, validator=attr.validators.instance_of(int))
    image_force = attr.ib(default=True, validator=attr.validators.instance_of(bool))

    cmd_mkfs = attr.ib(default='mkfs.ntfs', validator=attr.validators.instance_of(str))
    cmd_mount = attr.ib(default='mount.ntfs-3g', validator=attr.validators.instance_of(str))

    loopdev = None
    loopdir = None

    def __attrs_post_init__(self):
        self.status = ICStatus.unknown

        self.command = self.target.get_active_driver( #pylint: disable=no-member
            CommandProtocol
        )
        if not self.command:
            raise NoDriverFoundError(
                "Target has no {} Driver".format(CommandProtocol)
            )

        self.loopdev, _, exitcode = self.command.run('losetup -f')
        if exitcode != 0 or len(self.loopdev) == 0:
            raise ImageCreatorError("Cannot initialize ImageCreator: no free loop device left")

        self.loopdir, _, exitcode = self.command.run('mktemp -d')
        if exitcode != 0 or len(self.loopdir) == 0:
            raise ImageCreatorError("Cannot initialize ImageCreator: no temp folder available")

        if self.image_force == True:
            self.command.run('rm {}'.format(self.image_path))

        _, _, exitcode = self.command.run('ls {}'.format(self.image_path))
        if exitcode == 0:
            raise ImageCreatorError("Cannot initialize ImageCreator: image already exists")

        self.status = ICStatus.initialized

    @step()
    def _detach(self):
        # detach loop
        self.command.run_check('losetup -d {}'.format(self.loopdev[0]))
        stdout, _, _ = self.command.run('losetup -a | grep {}'.format(self.loopdev[0]))
        if len(stdout) > 0:
            self.status = ICStatus.unknown
            raise ImageCreatorError("ImageCreator problem: fail to detach loop")

    @step()
    def create(self):
        if self.status == ICStatus.initialized:
            # create raw image
            self.command.run_check('dd bs=1M count={} if=/dev/zero of={}'.format(self.image_size, self.image_path))
            # attach a loop device
            self.command.run_check('losetup {} {}'.format(self.loopdev[0], self.image_path))
            # partition image
            self.command.run_check('parted -s {} -- mklabel msdos mkpart primary fat32 64s 100%'.format(self.loopdev[0]))
            # create filesystem
            self.command.run_check('{mkfs} {dev}p1'.format(mkfs=self.cmd_mkfs, dev=self.loopdev[0]))
            # detach
            self._detach()
            # created empty
            self.status == ICStatus.created
        else:
            raise ImageCreatorError("ImageCreator problem: not initialized")


    @step()
    def put(self, filename=None, destination=None):
        destpath = self.loopdir[0]
        if self.status == ICStatus.created:
            # attach a loop device
            self.command.run_check('losetup {} {}'.format(self.loopdev[0], self.image_path))
            self.command.run_check('{mnt} -o loop {dev}p1 {folder}'.format(mnt=self.cmd_mount, dev=self.loopdev[0], folder=self.loopdir[0]))
            if filename == None:
                self.command.run_check('echo test > {}/testfile'.format(self.loopdir[0]))
            else:
                if destination != None:
                    destpath = '{}/{}'.format(self.loopdir[0], destination)
                    self.command.run_check('mkdir -p {}'.format(destpath))
                self.command.run_check('cp {} {}/'.format(filename, destpath))

            self.command.run_check('umount {folder}'.format(folder=self.loopdir[0]))
            # detach
            self._detach()
        else:
            raise ImageCreatorError("Cannot put file with ImageCreator")

    @step()
    def clean(self, remove_image=True):
        self.status = ICStatus.unknown
        self.command.run('umount {}'.format(self.loopdir[0]))
        self.command.run('rmdir {}'.format(self.loopdir[0]))
        self.command.run('losetup -d {}'.format(self.loopdev[0]))

        stdout, _, _ = self.command.run('losetup -a | grep {}'.format(self.loopdev[0]))
        if len(stdout) > 0:
            raise ImageCreatorError("ImageCreator problem: fail to detach loop")
        _, _, exitcode = self.command.run('ls {}'.format(self.loopdir[0]))
        if exitcode != 1:
            raise ImageCreatorError("ImageCreator problem: loopdir still exists")

        if remove_image == True:
            self.command.run_check('rm {}'.format(self.image_path))
            _, _, exitcode = self.command.run('ls {}'.format(self.image_path))
            if exitcode != 1:
                raise ImageCreatorError("ImageCreator problem: image still exists")

@attr.s(cmp=False)
class ImageCreatorError(Exception):
    """Exception which indicates a error in the state handling of the test"""
    msg = attr.ib()
