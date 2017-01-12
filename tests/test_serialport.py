from labgrid.resource import RawSerialPort  # pylint: disable=import-error


class TestSerialPort:
    def test_instanziation(self):
        s = RawSerialPort(None, 'port')
        assert (s.port == 'port')

    def test_instanziation_with(self, target):
        s = RawSerialPort(target, 'port', 115200)
        assert (s.port == 'port')
        assert (s.speed == 115200)
        assert s in target.resources
