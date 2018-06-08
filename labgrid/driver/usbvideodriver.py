# pylint: disable=no-member
import subprocess
import attr

from .common import Driver
from ..factory import target_factory
from ..resource.remote import NetworkUSBVideo
from ..resource.udev import USBVideo
from ..exceptions import InvalidConfigError

@target_factory.reg_driver
@attr.s(cmp=False)
class USBVideoDriver(Driver):
    bindings = {
        "video": {USBVideo, NetworkUSBVideo},
    }

    def get_caps(self):
        match = (self.video.vendor_id, self.video.model_id)
        if match == (0x046d, 0x082d):
            return ("mid", [
                ("low", "video/x-h264,width=640,height=360,framerate=5/1"),
                ("mid", "video/x-h264,width=1280,height=720,framerate=15/2"),
                ("high", "video/x-h264,width=1920,height=1080,framerate=10/1"),
                ])
        raise InvalidConfigError("Unkown USB video device {:04x}:{:04x}".format(*match))

    def select_caps(self, hint=None):
        default, variants = self.get_caps()
        variant = hint if hint else default
        for name, caps in variants:
            if name == variant:
                return caps
        raise InvalidConfigError("Unkown video format {} for device {:04x}:{:04x}".format(
            variant, self.video.vendor_id, self.video.model_id))

    @Driver.check_active
    def stream(self, caps_hint=None):
        caps = self.select_caps(caps_hint)

        tx_cmd = self.video.command_prefix + ["gst-launch-1.0"]
        tx_cmd += "v4l2src ! {} ! h264parse ! fdsink".format(caps).split()
        rx_cmd = ["gst-launch-1.0"]
        rx_cmd += "fdsrc ! h264parse ! avdec_h264 ! glimagesink sync=false".split()

        tx = subprocess.Popen(
            tx_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )
        rx = subprocess.Popen(
            rx_cmd,
            stdin=tx.stdout,
            stdout=subprocess.DEVNULL,
        )

        # wait until one subprocess has termianted
        while True:
            try:
                tx.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass
            try:
                rx.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass

        rx.terminate()
        tx.terminate()
