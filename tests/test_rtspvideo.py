from labgrid.resource.rtspvideostream import RTSPVideoStream
from labgrid.driver.rtspvideodriver import RTSPVideoDriver


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
