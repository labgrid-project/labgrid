import subprocess

import attr

from ..exceptions import InvalidConfigError
from ..factory import target_factory
from ..protocol import VideoProtocol
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class USBVideoDriver(Driver, VideoProtocol):
    bindings = {
        "video": {"USBVideo", "NetworkUSBVideo"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._prepared = False

    def get_qualities(self):
        match = (self.video.vendor_id, self.video.model_id)
        if match == (0x046d, 0x082d):
            return ("mid", [
                ("low", "video/x-h264,width=640,height=360,framerate=5/1"),
                ("mid", "video/x-h264,width=1280,height=720,framerate=15/2"),
                ("high", "video/x-h264,width=1920,height=1080,framerate=10/1"),
                ])
        elif match == (0x046d, 0x0892):
            return ("mid", [
                ("low", "image/jpeg,width=640,height=360,framerate=5/1"),
                ("mid", "image/jpeg,width=1280,height=720,framerate=15/2"),
                ("high", "image/jpeg,width=1920,height=1080,framerate=10/1"),
                ])
        elif match == (0x046d, 0x08e5): # Logitech HD Pro Webcam C920
            return ("mid", [
                ("low", "image/jpeg,width=640,height=360,framerate=5/1"),
                ("mid", "image/jpeg,width=1280,height=720,framerate=15/2"),
                ("high", "image/jpeg,width=1920,height=1080,framerate=10/1"),
                ])
        elif match == (0x1224, 0x2825): # LogiLink UA0371
            return ("mid", [
                ("low", "image/jpeg,width=640,height=480,framerate=30/1"),
                ("mid", "image/jpeg,width=1280,height=720,framerate=30/1"),
                ("high", "image/jpeg,width=1920,height=1080,framerate=30/1"),
                ])
        elif match == (0x05a3, 0x9331): # WansView Webcam 102
            return ("mid", [
                ("low","video/x-h264,width=640,height=360,framerate=30/1"),
                ("mid","video/x-h264,width=1280,height=720,framerate=30/1"),
                ("high","video/x-h264,width=1920,height=1080,framerate=30/1"),
                ])
        elif match == (0x534d, 0x2109): # MacroSilicon
            return ("mid", [
                ("low", "image/jpeg,width=720,height=480,framerate=10/1"),
                ("mid", "image/jpeg,width=1280,height=720,framerate=10/1"),
                ("high", "image/jpeg,width=1920,height=1080,framerate=10/1"),
                ])
        elif match == (0x1d6c, 0x0103): # HD 2MP WEBCAM
            return ("mid", [
                ("low", "video/x-h264,width=640,height=480,framerate=25/1"),
                ("mid", "video/x-h264,width=1280,height=720,framerate=25/1"),
                ("high", "video/x-h264,width=1920,height=1080,framerate=25/1"),
                ])
        elif match == (0x0c45, 0x636b): # LogiLink UA0379 / Microdia
            return ("mid", [
                ("low", "image/jpeg,width=640,height=480,pixel-aspect-ratio=1/1,framerate=30/1"),
                ("mid", "image/jpeg,width=1280,height=720,pixel-aspect-ratio=1/1,framerate=30/1"),
                ("high", "image/jpeg,width=1920,height=1080,pixel-aspect-ratio=1/1,framerate=30/1"),
                ])
        elif match == (0x0c45, 0x636d): # AUKEY PC-LM1E
            return ("mid", [
                ("low", "image/jpeg,width=640,height=480,pixel-aspect-ratio=1/1,framerate=30/1"),
                ("mid", "image/jpeg,width=864,height=480,pixel-aspect-ratio=1/1,framerate=30/1"),
                ("high", "image/jpeg,width=1280,height=1024,pixel-aspect-ratio=1/1,framerate=30/1"),
                ])
        self.logger.warning(
            "Unkown USB video device {:04x}:{:04x}, using fallback pipeline."
            .format(*match))
        return ("mid", [
            ("low", "image/jpeg,width=640,height=480,framerate=30/1"),
            ("mid", "image/jpeg,width=1280,height=720,framerate=30/1"),
            ("high", "image/jpeg,width=1920,height=1080,framerate=30/1"),
            ])

    def select_caps(self, hint=None):
        default, variants = self.get_qualities()
        variant = hint if hint else default
        for name, caps in variants:
            if name == variant:
                return caps
        raise InvalidConfigError(
            f"Unknown video format {variant} for device {self.video.vendor_id:04x}:{self.video.model_id:04x}"  # pylint: disable=line-too-long
        )

    def get_pipeline(self, path, caps, controls=None):
        match = (self.video.vendor_id, self.video.model_id)
        if match == (0x046d, 0x082d):
            controls = controls or "focus_auto=1"
            inner = "h264parse"
        elif match == (0x046d, 0x0892):
            controls = controls or "focus_auto=1"
            inner = None
        elif match == (0x046d, 0x08e5):
            controls = controls or "focus_auto=1"
            inner = None
        elif match == (0x1224, 0x2825): # LogiLink UA0371
            inner = None  # just forward the jpeg frames
        elif match == (0x05a3, 0x9331): # WansView Webcam 102
            inner = "h264parse"
        elif match == (0x534d, 0x2109):
            inner = None  # just forward the jpeg frames
        elif match == (0x1d6c, 0x0103):
            controls = controls or "focus_auto=1"
            inner = "h264parse"
        elif match == (0x0c54, 0x636b):
            controls = controls or "focus_auto=1"
            inner = None  # just forward the jpeg frames
        elif match == (0x0c54, 0x636d):
            controls = controls or "focus_auto=1"
            inner = None  # just forward the jpeg frames
        else: # fallback pipeline
            inner = None  # just forward the jpeg frames

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
        rx_cmd = ["gst-launch-1.0", "playbin3", "buffer-duration=0", "uri=fd://0"]

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

        # wait until one subprocess has terminated
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

        rx.communicate()
        tx.communicate()
