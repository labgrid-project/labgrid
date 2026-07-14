import subprocess
import sys
from urllib.parse import urlsplit

import attr

from .common import Driver
from ..factory import target_factory
from ..util.proxy import proxymanager
from ..protocol import VideoProtocol


@target_factory.reg_driver
@attr.s(eq=False)
class RTSPVideoDriver(Driver, VideoProtocol):
    bindings = {
        "video": "RTSPVideoStream",
    }

    latency = attr.ib(default=100, validator=attr.validators.instance_of(int))

    def get_qualities(self):
        return ("high", [("high", None)])

    @Driver.check_active
    def stream(self, quality_hint=None, controls=None):
        s = urlsplit(self.video.url)
        if s.scheme != "rtsp":
            print(f"Unknown scheme: {s.scheme}", file=sys.stderr)
            return

        url = proxymanager.get_url(self.video.url, default_port=554)
        pipeline = [
            "gst-launch-1.0",
            "rtspsrc",
            f"location={url}",
            f"latency={self.latency}",
            "!",
            "decodebin",
            "!",
            "autovideoconvert",
            "!",
            "autovideosink",
            "sync=false",
        ]

        sub = subprocess.run(pipeline)
        return sub.returncode
