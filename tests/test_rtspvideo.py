from labgrid.resource.rtspvideostream import RTSPVideoStream
from labgrid.driver.rtspvideodriver import (
    RTSPVideoDriver,
    parse_video_caps,
    parse_discoverer_info,
)


def test_ipvideo_create_rtsp(target):
    r = RTSPVideoStream(target, name=None, url="rtsp://localhost/stream1")
    d = RTSPVideoDriver(target, name=None)
    assert isinstance(d, RTSPVideoDriver)

def test_ipvideo_create_with_port(target):
    r = RTSPVideoStream(target, name=None, url="rtsp://localhost:8554/stream1")
    d = RTSPVideoDriver(target, name=None)
    assert isinstance(d, RTSPVideoDriver)

def test_ipvideo_create_with_latency(target):
    r = RTSPVideoStream(target, name=None, url="rtsp://localhost/stream1")
    d = RTSPVideoDriver(target, name=None, latency=500)
    assert isinstance(d, RTSPVideoDriver)
    assert d.latency == 500

def test_parse_video_caps():
    caps = ("video/x-raw, format=(string)I420, width=(int)640, height=(int)480, "
            "interlace-mode=(string)progressive, framerate=(fraction)30/1")
    info = parse_video_caps(caps)
    assert info["width"] == 640
    assert info["height"] == 480
    assert info["format"] == "I420"
    assert info["framerate"] == 30.0

def test_parse_video_caps_no_framerate():
    caps = "video/x-raw, format=(string)NV12, width=(int)1920, height=(int)1080, framerate=(fraction)0/1"
    info = parse_video_caps(caps)
    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["framerate"] == 0.0
    
def test_parse_video_caps_garabge_framerate():
    caps = "video/x-raw, format=(string)NV12, width=(int)1920, height=(int)1080, framerate=(fraction)30/0"
    info = parse_video_caps(caps)
    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["framerate"] == 0.0

def test_parse_video_caps_missing_fields():
    info = parse_video_caps("video/x-raw")
    assert "width" not in info
    assert "height" not in info
    assert info["framerate"] == 0.0

DISCOVERER_OUTPUT = """\
Analyzing rtsp://127.0.0.1:8554/test
Done discovering rtsp://127.0.0.1:8554/test

Properties:
  Duration: 99:99:99.999999999
  Seekable: no
  Live: yes
    video #1: image/jpeg, parsed=(boolean)true, framerate=(fraction)30/1, width=(int)640, height=(int)480
      Tags:
        None

      Codec:
        image/jpeg, parsed=(boolean)true, framerate=(fraction)30/1, width=(int)640, height=(int)480
      Stream ID: 359314d7d4bba383223927d7e57d4244d0800e629c626be81c505055c62170e2/video:0:0:RTP:AVP:26
      Width: 640
      Height: 480
      Depth: 24
      Frame rate: 30/1
      Pixel aspect ratio: 1/1
      Interlaced: false
      Bitrate: 0
      Max bitrate: 0
"""

def test_parse_discoverer_info():
    info = parse_discoverer_info(DISCOVERER_OUTPUT)
    assert info["codec"] == (
        "image/jpeg, parsed=(boolean)true, framerate=(fraction)30/1, "
        "width=(int)640, height=(int)480"
    )
    assert info["depth"] == 24

def test_parse_discoverer_info_missing_fields():
    info = parse_discoverer_info("Analyzing rtsp://localhost/test\n")
    assert "codec" not in info
    assert "depth" not in info
