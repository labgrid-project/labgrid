"""
This module implements the communication with TMC SCPI compatible instrument using py-visa driver.

Supported modules:

- All VISA compatible instruments supported by py-visa

Supported Functionality:

- Command, Query, Identify
"""

from importlib import import_module


class VISAInstrument:
    def __init__(self, device_identifier, backend):
        try:
            _py_pyvisa_module = import_module('pyvisa')
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError("pyvisa module not found, please install it") from e
        else:
            _pyvisa_resource_manager = _py_pyvisa_module.ResourceManager(backend)
            if _pyvisa_resource_manager is None:
                raise ValueError("pyVISA backend not found")
            self._pyvisa_device = _pyvisa_resource_manager.open_resource(device_identifier)
            if self._pyvisa_device is None:
                raise ValueError("pyVISA device not found")

    def write(self, cmd):
        self._pyvisa_device.write(cmd)

    def query(self, cmd):
        return self._pyvisa_device.query(cmd)

    def __del__(self):
        if hasattr(self, '_pyvisa_device') and self._pyvisa_device is not None:
            self._pyvisa_device.close()
            self._pyvisa_device = None


def handle_write(device_identifier, backend, cmd):
    visa_inst = VISAInstrument(device_identifier, backend)
    visa_inst.write(cmd)

def handle_query(device_identifier, backend, cmd):
    visa_inst = VISAInstrument(device_identifier, backend)
    return visa_inst.query(cmd)

methods = {
    "write": handle_write,
    "query": handle_query,
}
