import re
import select
import subprocess
import sys
import time
from urllib.parse import urlsplit

import attr

from .common import Driver
from .exception import ExecutionError
from ..factory import target_factory
from ..util.proxy import proxymanager
from ..protocol import VideoProtocol


def parse_video_caps(caps):
    """Parse a GStreamer video caps string into a dict.

    Example input:
        video/x-raw, format=(string)I420, width=(int)640, height=(int)480,
        framerate=(fraction)30/1

    Returns a dict with the keys width (int), height (int), format (str) and
    framerate (float, 0.0 if not signalled) for the fields present in the
    caps, plus the raw caps string under "caps".
    """
    info = {"caps": caps.strip()}
    m = re.search(r"width=\(int\)(\d+)", caps)
    if m:
        info["width"] = int(m.group(1))
    m = re.search(r"height=\(int\)(\d+)", caps)
    if m:
        info["height"] = int(m.group(1))
    m = re.search(r"format=\(string\)([A-Za-z0-9_-]+)", caps)
    if m:
        info["format"] = m.group(1)
    m = re.search(r"framerate=\(fraction\)(\d+)/(\d+)", caps)
    if m and int(m.group(2)):
        info["framerate"] = int(m.group(1)) / int(m.group(2))
    else:
        info["framerate"] = 0.0
    return info


def parse_discoverer_info(text):
    """Parse the output of `gst-discoverer-1.0 --verbose` into a dict.

    Example input (abridged):
          Codec:
            image/jpeg, parsed=(boolean)true, width=(int)640, height=(int)480
          Depth: 24

    Returns a dict with the keys codec (str) and depth (int) for the fields
    present in the output. The codec string is kept verbatim, as which fields
    it contains differs per codec.
    """
    info = {}
    m = re.search(r"^\s*Codec:\s*\n\s*(\S.*)$", text, re.MULTILINE)
    if m:
        info["codec"] = m.group(1).strip()
    m = re.search(r"^\s*Depth:\s*(\d+)\s*$", text, re.MULTILINE)
    if m:
        info["depth"] = int(m.group(1))
    return info


@target_factory.reg_driver
@attr.s(eq=False)
class RTSPVideoDriver(Driver, VideoProtocol):
    bindings = {
        "video": "RTSPVideoStream",
    }

    latency = attr.ib(default=100, validator=attr.validators.instance_of(int))

    def get_qualities(self):
        return ("high", [("high", None)])

    def _get_url(self):
        s = urlsplit(self.video.url)
        if s.scheme != "rtsp":
            raise ExecutionError(f"Unknown scheme: {s.scheme}")
        return proxymanager.get_url(self.video.url, default_port=554)

    @Driver.check_active
    def stream(self, quality_hint=None, controls=None):
        try:
            url = self._get_url()
        except ExecutionError as e:
            print(e.msg, file=sys.stderr)
            return

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

    def _probe(self, timeout=10.0, measure_time=3.0):
        """Run the fakesink pipeline once and return the stream properties.

        Shared engine behind get_stream_info(), get_resolution() and
        get_framerate(): parses the negotiated caps and, when measure_time > 0,
        counts decoded frames for that many seconds. Kept intentionally lean so
        the lightweight getters do not pay for work they do not need; any
        heavier probing added later belongs in get_stream_info() around this
        call, not here.
        """
        url = self._get_url()

        pipeline = [
            "gst-launch-1.0",
            "-v",
            "rtspsrc",
            f"location={url}",
            f"latency={self.latency}",
            "!",
            "decodebin",
            "!",
            "fakesink",
            "sync=false",
            "silent=false",
        ]

        sub = subprocess.Popen(
            pipeline, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        info = None
        frames = 0
        first_frame = None
        last_frame = None
        caps_deadline = time.monotonic() + timeout
        measure_end = None
        try:
            while True:
                now = time.monotonic()
                if info is None and now > caps_deadline:
                    raise ExecutionError(
                        f"could not determine stream caps within {timeout} seconds"
                    )
                if measure_end is not None and now >= measure_end:
                    break
                ready, _, _ = select.select([sub.stdout], [], [], 0.25)
                if not ready:
                    if sub.poll() is not None:
                        raise ExecutionError(
                            f"gst-launch-1.0 exited with {sub.returncode} before "
                            "the stream caps could be determined"
                        )
                    continue
                line = sub.stdout.readline()
                if not line:
                    if info is not None:
                        break
                    raise ExecutionError(
                        f"gst-launch-1.0 exited with {sub.wait()} before "
                        "the stream caps could be determined"
                    )
                if (
                    info is None
                    and "GstFakeSink" in line
                    and ".GstPad:sink: caps = video/x-raw" in line
                ):
                    info = parse_video_caps(line.split(" caps = ", 1)[1])
                    if measure_time <= 0:
                        break
                    measure_end = time.monotonic() + measure_time
                elif info is not None and "last-message = chain" in line:
                    frames += 1
                    if first_frame is None:
                        first_frame = now
                    last_frame = now
        finally:
            sub.terminate()
            try:
                sub.wait(timeout=2)
            except subprocess.TimeoutExpired:
                sub.kill()
                sub.wait()

        info["measured_fps"] = (
            (frames - 1) / (last_frame - first_frame) if frames >= 2 else 0.0
        )
        return info

    def _discover(self, timeout=10.0):
        """Run gst-discoverer-1.0 once and return codec-level properties.

        _probe() reads the caps at the fakesink, i.e. after decodebin, where
        the stream is already raw video: the codec is gone and the colour depth
        was never part of the caps. gst-discoverer inspects the encoded stream
        instead, so it can report both.
        """
        url = self._get_url()

        try:
            sub = subprocess.run(
                ["gst-discoverer-1.0", "--verbose", url],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise ExecutionError(
                f"gst-discoverer-1.0 did not finish within {timeout} seconds"
            ) from None
        if sub.returncode != 0:
            raise ExecutionError(
                f"gst-discoverer-1.0 exited with {sub.returncode}"
            )

        return parse_discoverer_info(sub.stdout)

    @Driver.check_active
    def get_stream_info(self, timeout=10.0, measure_time=3.0):
        """Connect to the stream without a display and return its properties.

        Decodes the stream into a fakesink and parses the negotiated caps,
        counts the decoded frames for measure_time seconds, and additionally
        queries gst-discoverer for the properties that are not part of the
        decoded caps.

        Args:
            timeout (float): maximum time in seconds to wait for the caps
            measure_time (float): how long to count frames for measured_fps;
                0 skips the measurement (faster, measured_fps will be 0.0)

        Returns a dict with:
            width, height (int): frame size from the negotiated caps
            format (str): pixel format from the negotiated caps
            framerate (float): nominal framerate from the caps; often 0.0
                for RTSP, as the SDP usually does not signal one
            measured_fps (float): frame rate measured over measure_time
            caps (str): the full negotiated caps string
            codec (str): the encoded stream's codec, e.g. "image/jpeg, ..."
            depth (int): colour depth in bits per pixel
        """
        info = self._probe(timeout=timeout, measure_time=measure_time)
        info.update(self._discover(timeout=timeout))
        return info

    @Driver.check_active
    def get_resolution(self):
        """Return the stream resolution as a (width, height) tuple.

        Only probes the negotiated caps; the frame rate is not measured.
        """
        info = self._probe(measure_time=0)
        return (info["width"], info["height"])

    @Driver.check_active
    def get_framerate(self, measure_time=3.0):
        """Return the measured frame rate of the stream in frames per second."""
        info = self._probe(measure_time=measure_time)
        return info["measured_fps"]
