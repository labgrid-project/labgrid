"""The SSHFS module provides support to mount a filesystem through SSH """
import enum
import os

import attr

from ..exceptions import NoDriverFoundError, NoResourceFoundError
from ..protocol import CommandProtocol
from ..step import step


class SSHFSStatus(enum.Enum):
    """This class describes the SSHFS Status"""
    umounted = 1
    mounted = 2


@attr.s(cmp=False)
class SSHFS(object):
    """The SSHFS class provides an easy to use interface to mount a filesystem through SSH """
    target = attr.ib()
    mntkey = attr.ib(validator=attr.validators.instance_of(str))
    localpath = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.command = self.target.get_active_driver( #pylint: disable=no-member
            CommandProtocol
        )
        if not self.command:
            raise NoDriverFoundError(
                "Target has no {} Driver".format(CommandProtocol)
            )

        self.rsc = self.target.get_resource('NetworkService', name=self.mntkey)
        if not self.rsc:
            raise NoResourceFoundError(
                "Target has no {} Resource".format(NetworkService)
            )
        
        self.remotepath = self.target.env.config.get_image_path(self.mntkey)
        if not self.remotepath:
            raise SSHFSError(
                "Target has no {} folder".format(self.mntkey)
            )

        self.command.run('umount {}'.format(self.localpath))
        self.command.run('rmdir {}'.format(self.localpath))

        _, _, returncode = self.command.run('ls {}'.format(self.localpath))
        if returncode != 1:
            raise SSHFSError(
                "SSHFS init failed"
            )

        self.status = SSHFSStatus.umounted

    @step()
    def mount(self):
        mountcmd = "sshfs -o ssh_command='sshpass -p {pswd} ssh' {user}@{hst}:{rpath} {lpath}".format(pswd=self.rsc.password, user=self.rsc.username, hst=self.rsc.address, rpath=self.remotepath, lpath=self.localpath)
        if self.status == SSHFSStatus.umounted:
            self.command.run_check('mkdir -p {}'.format(self.localpath))
            self.command.run_check(mountcmd)
            self.status = SSHFSStatus.mounted

    @step()
    def umount(self):
        if self.status == SSHFSStatus.mounted:
            self.command.run_check('umount {}'.format(self.localpath))
            self.command.run_check('rmdir {}'.format(self.localpath))
            self.status = SSHFSStatus.umounted

@attr.s(cmp=False)
class SSHFSError(Exception):
    """Exception which indicates a error in the state handling of the test"""
    msg = attr.ib()
