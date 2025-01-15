import serial

class USBKMTronicRelay:
    def set_output(self, path, index, status):
        # second and third is index and status on/off
        # \xFF\x01\x00 = turn relay 1 off
        # \xFF\x01\x01 = turn relay 1 on
        cmd = bytes([255, index, int(status == True)])
        with serial.Serial(path, 9600) as ser:
            ser.write(cmd)

    def get_output(self, path, index):
        # \xFF\x01\x03 will read relay 1 status
        cmd = bytes([255, index, 3])
        with serial.Serial(path, 9600) as ser:
            ser.write(cmd)
            data = ser.read(3)
        return data[2]

_relays = {}

def _get_relay(path):
    if (path) not in _relays:
        _relays[(path)] = USBKMTronicRelay()
    return _relays[(path)]

def handle_set(path, index, status):
    relay = _get_relay(path)
    relay.set_output(path, index, status)

def handle_get(path, index):
    relay = _get_relay(path)
    return relay.get_output(path, index)

methods = {
    "set": handle_set,
    "get": handle_get,
}
