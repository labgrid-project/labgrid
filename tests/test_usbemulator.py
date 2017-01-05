import pytest

from labgrid.driver.fake import FakeCommandDriver
from labgrid.external import USBStick


class TestUSBStick:
    def test_create(self, target):
        d = FakeCommandDriver(target)
        u = USBStick(target, 'imagename')
        assert (isinstance(u, USBStick))
