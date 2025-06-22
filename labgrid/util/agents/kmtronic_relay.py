import serial

class USBKMTronicRelay:
    def set_output(self, path, index, status):
        # second and third is index and status on/off
        # \xFF\x01\x00 = turn relay 1 off
        # \xFF\x01\x01 = turn relay 1 on
        cmd = bytes([255, index, int(status == True)])
        with serial.Serial(path, 9600) as ser:
            ser.write(cmd)

    def get_output(self, path, index, ports):
        # \xFF\x01\x03 will read relay 1 status
        # \xFF\x09\x00 will read from all relays, only works on 4 and 8 relay controller
        cmd = bytes([255, index, 3])
        if ports > 2:
            cmd = bytes([255, 9, 0])
        with serial.Serial(path, 9600, timeout=10) as ser:
            ser.write(cmd)
            if ports > 2:
                data = ser.read(ports)
                if data[0] == 255:
                    print("WARNING: Unexpected return value from KMTronic relay.")
                    print("Make sure to configure ports correctly in your config.2")
                    return -1
                state = data[index-1]
            else:
                data = ser.read(3)
                if data[0] != 255:
                    print("WARNING: Unexpected return value from KMTronic relay.")
                    print("Make sure to configure ports correctly in your config.1")
                    return -1
                state = data[2]
        return state

_relays = {}

def _get_relay(path):
    if (path) not in _relays:
        _relays[(path)] = USBKMTronicRelay()
    return _relays[(path)]

def handle_set(path, index, status):
    relay = _get_relay(path)
    relay.set_output(path, index, status)

def handle_get(path, index, ports):
    relay = _get_relay(path)
    return relay.get_output(path, index, ports)

methods = {
    "set": handle_set,
    "get": handle_get,
}
