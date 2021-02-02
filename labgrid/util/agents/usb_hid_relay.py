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
        if self._dev.is_kernel_driver_active(0):
            self._dev.detach_kernel_driver(0)

    def set_output(self, number, status):
        assert 1 <= number <= 8
        req = [0xFF if status else 0xFD, number]
        resp = self._dev.ctrl_transfer(
            usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_RECIPIENT_DEVICE | usb.util.ENDPOINT_OUT,
            SET_REPORT,
            (REPORT_TYPE_FEATURE << 8) | 0, # no report ID
            0,
            req, # payload
        )

    def get_output(self, number):
        assert 1 <= number <= 8
        resp = self._dev.ctrl_transfer(
            usb.util.CTRL_TYPE_CLASS | usb.util.CTRL_RECIPIENT_DEVICE | usb.util.ENDPOINT_IN,
            GET_REPORT,
            (REPORT_TYPE_FEATURE << 8) | 0, # no report ID
            0,
            8, # size
        )
        return bool(resp[7] & (1 << (number-1)))

    def __del__(self):
        usb.util.release_interface(self._dev, 0)


def handle_set(busnum, devnum, number, status):
    relay = USBHIDRelay(bus=busnum, address=devnum)
    relay.set_output(number, status)


def handle_get(busnum, devnum, number):
    relay = USBHIDRelay(bus=busnum, address=devnum)
    return relay.get_output(number)


methods = {
    'set': handle_set,
    'get': handle_get,
}
