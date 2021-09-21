"""
This module implements the communication protocol to switch the digital outputs
on the Deditec Relais8 board.

Supported modules:

- Relais8

Supported Functionality:

- Turn digital output on and off
"""
import logging

from binascii import unhexlify, hexlify

import usb.core
import usb.util


class Relais8:
    _padding = 'FEFEFEFEFEFEFEFEFF'
    _post_padding = '000000'

    _configuration_sequence = [
        '3430FF',
        '3434FF',
        '34C0FF',
        '3400FF',
        '3402FF',
        '340CFF',
        '340EFF',
        '3404FF',
        '3406FF',
        '3408FF',
        '340AFF',
        '3410FF',
        '3412FF',
        '3414FF',
        '3416FF',
        '34F4FF',
        '34F5FF',
        '34F6FF',
        '34F7FF',
        '34F0FF',
        '34ECFF']

    def __init__(self, **args):
        self._dev = usb.core.find(**args)
        if self._dev is None:
            raise ValueError("Device not found")
        if self._dev.is_kernel_driver_active(0):
            self._dev.detach_kernel_driver(0)

        cfg = self._dev.get_active_configuration()
        intf = cfg[(0, 0)]
        self._dev.set_configuration()
        usb.util.claim_interface(self._dev, 0)
        self._dev.ctrl_transfer(64, 0, 0, 0, 0, 5000)
        self._dev.ctrl_transfer(64, 3, 20, 0, 0, 5000)
        self._dev.ctrl_transfer(64, 9, 2, 0, 0, 5000)
        self._ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_OUT
        )
        self._ep_in = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_IN
        )
        self._sequence_number = 0
        self._logger = logging.getLogger("Device: ")
        self._run_configuration_sequence()

    def _run_configuration_sequence(self):
        for d in Relais8._configuration_sequence:
            self.write_config_request(d)
            self.read(255)

    def read(self, size):
        data = self._ep_in.read(size)
        self._logger.debug("Read data: %s", hexlify(data))
        return data

    def write_config_request(self, address):
        complete_request = unhexlify(Relais8._padding)
        complete_request += bytes([self._sequence_number])
        complete_request += unhexlify(address + Relais8._post_padding)
        self._logger.debug("Sending Request: %s", hexlify(complete_request))
        self.write(complete_request)

    def write(self, data):
        self._sequence_number = (self._sequence_number + 1) & 0xff
        self._logger.debug("Writing data: %s", hexlify(data))
        self._ep_out.write(data)

    def set_all_outputs(self, status, reset=False):
        assert isinstance(status, int)
        if status == 0:
            reset = True
        if status > 255 or status < 0:
            return
        data = f'0123{0 if reset else 8}000000001{status:02X}00000000000000'
        self.write(unhexlify(Relais8._padding + data))
        self.read(255)

    def set_output(self, number, status):
        if status:
            data = f'238000000001{1 << number - 1:02X}00000000000000'
        else:
            data = f'23A000000001{1 << number - 1:02X}00000000000000'
        complete_request = unhexlify(Relais8._padding)
        complete_request += bytes([self._sequence_number])
        complete_request += unhexlify(data)
        self.write(complete_request)
        self.read(255)

    def get_output(self, number):
        data = '34000000000F'
        complete_request = unhexlify(Relais8._padding)
        complete_request += bytes([self._sequence_number])
        complete_request += unhexlify(data)
        self.write(complete_request)
        read_data = self.read(255).tobytes()
        index = read_data.find(b'\x1a')
        if read_data[index+1] == self._sequence_number - 1:
            outputs = read_data[index+2]
        else:
            raise IOError("Could not read outputs from device")
        return outputs & (1 << (number - 1)) > 0

    def __del__(self):
        usb.util.release_interface(self._dev, 0)


def handle_set(busnum, devnum, number, status):
    relais8 = Relais8(bus=busnum, address=devnum)
    relais8.set_output(number, status)


def handle_get(busnum, devnum, number):
    relais8 = Relais8(bus=busnum, address=devnum)
    return relais8.get_output(number)


methods = {
    'set': handle_set,
    'get': handle_get,
}
