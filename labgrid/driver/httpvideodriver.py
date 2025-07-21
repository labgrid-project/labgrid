import pathlib
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
class HTTPVideoDriver(Driver, VideoProtocol):
    bindings = {
        "video": "HTTPVideoStream",
    }

    def get_qualities(self):
        return ("high", [("high", None)])

    def _get_default_port(self):
        default_port = None
        s = urlsplit(self.video.url)
        if s.scheme == "http":
            default_port = 80
        elif s.scheme == "https":
            default_port = 443
        else:
            print(f"Unknown scheme: {s.scheme}", file=sys.stderr)
            return default_port

    @Driver.check_active
    def stream(self, quality_hint=None):
        default_port = self._get_default_port()
        if default_port is None:
            return

        url = proxymanager.get_url(self.video.url, default_port=default_port)
        pipeline = [
            "gst-launch-1.0",
            "souphttpsrc",
            f"location={url}",
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

    @Driver.check_active
    def screenshot(self, filename):
        default_port = self._get_default_port()
        if default_port is None:
            return

        filepath = pathlib.Path(filename)
        url = proxymanager.get_url(self.video.url, default_port=default_port)
        pipeline = [
            "gst-launch-1.0",
            "souphttpsrc",
            "num-buffers=75",
            f"location={url}",
            "!",
            "decodebin",
            "!",
            "jpegenc",
            "!",
            "filesink",
            f"location={filepath.absolute()}",
        ]

        sub = subprocess.run(pipeline)
        return sub.returncode
