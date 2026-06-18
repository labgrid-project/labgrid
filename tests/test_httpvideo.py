from labgrid.resource.httpvideostream import HTTPVideoStream
from labgrid.driver.httpvideodriver import HTTPVideoDriver


def test_ipvideo_create_http(target):
    r = HTTPVideoStream(target, name=None, url="http://localhost/")
    d = HTTPVideoDriver(target, name=None)
    assert isinstance(d, HTTPVideoDriver)

def test_ipvideo_create_https(target):
    r = HTTPVideoStream(target, name=None, url="https://localhost/")
    d = HTTPVideoDriver(target, name=None)
    assert isinstance(d, HTTPVideoDriver)

def test_ipvideo_create_with_port(target):
    r = HTTPVideoStream(target, name=None, url="http://localhost:8080/")
    d = HTTPVideoDriver(target, name=None)
    assert isinstance(d, HTTPVideoDriver)
