from importlib import import_module
import attr

from ..factory import target_factory
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class PyVISADriver(Driver):
    """The PyVISADriver provides a transparent layer to the PyVISA module allowing to get a pyvisa resource

        Args:
            bindings (dict): driver to use with PyVISA
        """
    bindings = {"pyvisa_resource": "PyVISADevice"}

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        _py_pyvisa_module = import_module('pyvisa')
        self._pyvisa_resource_manager = _py_pyvisa_module.ResourceManager(self.pyvisa_resource.backend)
        self.pyvisa_device = None

    def on_activate(self):
        device_identifier = f'{self.pyvisa_resource.type}::{self.pyvisa_resource.url}::INSTR'
        self.pyvisa_device = self._pyvisa_resource_manager.open_resource(device_identifier)

    def on_deactivate(self):
        self.pyvisa_device = None

    @Driver.check_active
    def get_session(self):
        return self.pyvisa_device
