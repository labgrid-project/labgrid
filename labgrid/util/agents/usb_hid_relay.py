"""
This module implements the communication protocol to switch the digital outputs
on a "dcttech" USB Relay.

Supported modules:

- USBRelay2 (and likely others)

Supported Functionality:

- Turn digital output on and off
"""

import usb.core
import usb.util

GET_REPORT = 0x1
SET_REPORT = 0x9
REPORT_TYPE_FEATURE = 3


class USBHIDRelay:
    def __init__(self, **args):
        self._dev = usb.core.find(**args)
        if self._dev is None:
            raise ValueError("Device not found")

        if self._dev.idVendor == 0x16C0:
            self.set_output = self.set_output_dcttech
            self.get_output = self.get_output_dcttech
        elif self._dev.idVendor == 0x5131:
            self.set_output = self.set_output_lcus
            self.get_output = self.get_output_lcus
        else:
            raise ValueError(f"Unknown vendor/protocol for VID {self._dev.idVendor:x}")

        if self._dev.is_kernel_driver_active(0):
            self._dev.detach_kernel_driver(0)

    def set_output_dcttech(self, number, status):
        assert 1 <= number <= 8
        req = [0xFF if status else 0xFD, number]
        self._dev.ctrl_transfer(
            usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_RECIPIENT_DEVICE | usb.util.ENDPOINT_OUT,
            SET_REPORT,
            (REPORT_TYPE_FEATURE << 8) | 0,  # no report ID
            0,
            req,  # payload
        )

    def get_output_dcttech(self, number):
        assert 1 <= number <= 8
        resp = self._dev.ctrl_transfer(
            usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_RECIPIENT_DEVICE | usb.util.ENDPOINT_IN,
            GET_REPORT,
            (REPORT_TYPE_FEATURE << 8) | 0,  # no report ID
            0,
            8,  # size
        )
        return bool(resp[7] & (1 << (number - 1)))

    def set_output_lcus(self, number, status):
        assert 1 <= number <= 8
        ep_in = self._dev[0][(0, 0)][0]
        ep_out = self._dev[0][(0, 0)][1]
        req = [0xA0, number, 0x01 if status else 0x00, 0x00]
        req[3] = sum(req) & 0xFF
        ep_out.write(req)
        ep_in.read(64)

    def get_output_lcus(self, number):
        assert 1 <= number <= 8
        # we have no information on how to read the current value
        return False

    def __del__(self):
        usb.util.release_interface(self._dev, 0)


_relays = {}


def _get_relay(busnum, devnum):
    if (busnum, devnum) not in _relays:
        _relays[(busnum, devnum)] = USBHIDRelay(bus=busnum, address=devnum)
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
