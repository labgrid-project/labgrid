from labgrid.resource.httpvideostream import HTTPVideoStream
from labgrid.driver.httpvideodriver import HTTPVideoDriver


def test_ipvideo_create(target):
    r = HTTPVideoStream(target, name=None, url="http://localhost/")
    d = HTTPVideoDriver(target, name=None)
    assert isinstance(d, HTTPVideoDriver)
