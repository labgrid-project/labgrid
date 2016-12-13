import subprocess
import attr

HOST = '192.168.24.137'
IMAGE_NAME = 'backing_store'

@attr.s
class USBStick(object):
    host  = attr.ib(validator=attr.validators.instance_of(str))
    image_name  = attr.ib(validator=attr.validators.instance_of(str))

    _UNPLUGGED = 1
    _PLUGGED = 2

    def __post_attr_init__(self):
        self.ssh("mount /dev/mmcblk1p1 /mnt")

    def plug_in(self):
        self.ssh("modprobe g_mass_storage file=/mnt/{image}".format(image=self.image_name))

    def eject(self):
        self.ssh("modprobe -r g_mass_storage")

    def upload_file(self, filename):
        subprocess.call('scp {filname} {host}:/tmp/{filename}').format(filename=filename)

    def upload_image(self, image):
        if not self.status == USBStick.UNPLUGGED:
            raise StatError("Device stioll plugged in, can't insert new image")
        subprocess.call('scp {filname} {host}:/tmp/{image}').format(filename=image)

    def ssh(self, cmd):
        try:
            call = subprocess.call('ssh {host} {cmd}').format(host=self.host, cmd=cmd)
        except:
            raise ExecutioError('Call failed: {}'.format(call))

    def __del__(self):
        self.ssh("modprobe -r g_mass_storage")

class ExecutioError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return "ExecutioError({msg})".format(msg=self.msg)

class StatError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return "StatError({msg})".format(msg=self.msg)
