import warnings
import attr

from ..factory import target_factory
from .base import SerialPort


@target_factory.reg_resource
@attr.s(eq=False)
class ModbusRTU():
    def __new__(cls, *args, **kwargs):
        warnings.warn(
            "The ModbusRTU class is deprecated. Use SerialPort instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return SerialPort(*args, **kwargs)
