# pylint: disable=no-member
import subprocess
import attr

from .common import Driver
from ..factory import target_factory
from ..exceptions import InvalidConfigError
from ..protocol import VideoProtocol

@target_factory.reg_driver
@attr.s(eq=False)
class USBVideoDriver(Driver, VideoProtocol):
    bindings = {
        "video": {"USBVideo", "NetworkUSBVideo"},
    }

    def get_qualities(self):
        match = (self.video.vendor_id, self.video.model_id)
        if match == (0x046d, 0x082d):
            return ("mid", [
                ("low", "video/x-h264,width=640,height=360,framerate=5/1"),
                ("mid", "video/x-h264,width=1280,height=720,framerate=15/2"),
                ("high", "video/x-h264,width=1920,height=1080,framerate=10/1"),
                ])
        if match == (0x046d, 0x0892):
            return ("mid", [
                ("low", "image/jpeg,width=640,height=360,framerate=5/1"),
                ("mid", "image/jpeg,width=1280,height=720,framerate=15/2"),
                ("high", "image/jpeg,width=1920,height=1080,framerate=10/1"),
                ])
        if match == (0x534d, 0x2109): # MacroSilicon
            return ("mid", [
                ("low", "image/jpeg,width=720,height=480,framerate=10/1"),
                ("mid", "image/jpeg,width=1280,height=720,framerate=10/1"),
                ("high", "image/jpeg,width=1920,height=1080,framerate=10/1"),
                ])
        raise InvalidConfigError("Unkown USB video device {:04x}:{:04x}".format(*match))

    def select_caps(self, hint=None):
        default, variants = self.get_qualities()
        variant = hint if hint else default
        for name, caps in variants:
            if name == variant:
                return caps
        raise InvalidConfigError(
            f"Unkown video format {variant} for device {self.video.vendor_id:04x}:{self.video.model_id:04x}"  # pylint: disable=line-too-long
        )

    def get_pipeline(self, path, caps, controls=None):
        match = (self.video.vendor_id, self.video.model_id)
        if match == (0x046d, 0x082d):
            controls = controls or "focus_auto=1"
            inner = "h264parse"
        elif match == (0x046d, 0x0892):
            controls = controls or "focus_auto=1"
            inner = None
        elif match == (0x534d, 0x2109):
            inner = None  # just forward the jpeg frames
        else:
            raise InvalidConfigError("Unkown USB video device {:04x}:{:04x}".format(*match))

        pipeline = f"v4l2src device={path} "
        if controls:
            pipeline += f"extra-controls=c,{controls} "
        pipeline += f"! {caps} "
        if inner:
            pipeline += f"! {inner} "
        pipeline += "! matroskamux streamable=true ! fdsink"
        return pipeline

    @Driver.check_active
    def stream(self, caps_hint=None, controls=None):
        caps = self.select_caps(caps_hint)
        pipeline = self.get_pipeline(self.video.path, caps, controls)

        tx_cmd = self.video.command_prefix + ["gst-launch-1.0", "-q"]
        tx_cmd += pipeline.split()
        rx_cmd = ["gst-launch-1.0"]
        rx_cmd += "playbin uri=fd://0".split()

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
