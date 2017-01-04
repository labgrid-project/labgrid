import pytest

from labgrid.external import USBStick


class TestUSBStick:
    def test_create(self):
        u = USBStick('dummyhost', 'imagename')
        assert (isinstance(u, USBStick))
