from labgrid.resource import SerialPort # pylint: disable=import-error

class TestSerialPort:
    def test_instanziation(self, target):
        s = SerialPort('port')
        assert(s.port == 'port')

    def test_instanziation_with(self, target):
        s = SerialPort('port',115200)
        assert(s.port == 'port')
        assert(s.speed == 115200)
