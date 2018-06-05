from labgrid.driver.fake import FakeCommandDriver, FakeFileTransferDriver
from labgrid.external import USBStick


class TestUSBStick:
    def test_create(self, target):
        d = FakeCommandDriver(target, "command")
        f = FakeFileTransferDriver(target, "filetransfer")
        target.activate(d)
        target.activate(f)
        u = USBStick(target, 'imagepath', 'imagename')
        assert (isinstance(u, USBStick))
