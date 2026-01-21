"""
This module implements the communication protocol to switch the digital outputs
on a Denkovi USB Relay.

Supported Functionality:

- Turn digital output on and off
"""

import usb.core
import usb.util

from pylibftdi import BitBangDevice
from threading import Lock


class DenkoviRelay:
    lock = Lock()

    def __init__(self, **args):
        self._dev = usb.core.find(**args)

        if self._dev is None:
            raise ValueError("Device not found")

        self._serialNumber = usb.util.get_string(self._dev, self._dev.iSerialNumber)

        if self._serialNumber is None:
            raise ValueError("Failed to get device serial number")

        self.lock.acquire()

        bitbangDev = BitBangDevice(self._serialNumber)

        if bitbangDev is None:
            raise ValueError("Failed to instantiate bitbang device")

        bitbangDev.direction = 0xFF

        bitbangDev.close()

        self.lock.release()

    def set_output(self, number, status):
        assert 1 <= number <= 8
        number = number - 1

        self.lock.acquire()

        bitbangDev = BitBangDevice(self._serialNumber)

        if bitbangDev is None:
            raise ValueError("Failed to instantiate bitbang device")

        if status:
            bitbangDev.port = bitbangDev.port | (1 << number)
        else:
            bitbangDev.port = bitbangDev.port & ~(1 << number)

        bitbangDev.close()

        self.lock.release()

    def get_output(self, number):
        assert 1 <= number <= 8
        number = number - 1

        val = None

        self.lock.acquire()

        bitbangDev = BitBangDevice(self._serialNumber)

        if bitbangDev is None:
            raise ValueError("Failed to instantiate bitbang device")

        if bitbangDev.port & (1 << number):
            val = True
        else:
            val = False

        bitbangDev.close()

        self.lock.release()

        return val

    def __del__(self):
        usb.util.release_interface(self._dev, 0)


_relays = {}


def _get_relay(busnum, devnum):
    if (busnum, devnum) not in _relays:
        _relays[(busnum, devnum)] = DenkoviRelay(bus=busnum, address=devnum)
    return _relays[(busnum, devnum)]


def handle_set(busnum, devnum, number, status):
    relay = _get_relay(busnum, devnum)
    relay.set_output(number, status)


def handle_get(busnum, devnum, number):
    relay = _get_relay(busnum, devnum)
    return relay.get_output(number)


methods = {
    "set": handle_set,
    "get": handle_get,
}
