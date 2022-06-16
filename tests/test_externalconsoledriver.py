import time

from labgrid.driver import ExternalConsoleDriver


class TestExternalConsoleDriver:
    def test_create(self, target):
        d = ExternalConsoleDriver(target, 'console', cmd='cat')
        assert (isinstance(d, ExternalConsoleDriver))

    def test_communicate(self, target):
        data = b"test\ndata"
        d = ExternalConsoleDriver(target, 'console', cmd='cat')
        target.activate(d)
        d.write(data)
        time.sleep(0.1)
        assert d.read(1024) == data  # assert written data is read
        d.write(data)
        time.sleep(0.1)
        assert d.read(5, max_size=5) == data[:5]  # assert max_size limits read bytes
        d.close()
