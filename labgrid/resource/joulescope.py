import attr

from ..factory import target_factory
from .udev import USBResource

# Joulescope USB product ids (application mode) mapped to their model name.  The
# vendor id ``16d0`` is shared with other manufacturers, so the product id is
# what actually identifies a Joulescope.  Bootloader-mode product ids (``0e87``,
# ``10b9``, ``1359``) are intentionally excluded: they cannot measure.
JOULESCOPE_MODELS = {
    "0e88": "js110",
    "10ba": "js220",
    "135a": "js320",
}


@target_factory.reg_resource
@attr.s(eq=False)
class JoulescopeDevice(USBResource):
    """The JoulescopeDevice describes a Joulescope energy analyzer.

    It is a :class:`USBResource`, so the usual udev ``match`` mechanism selects a
    specific device (for example by ``ID_SERIAL_SHORT`` or ``ID_PATH``) when more
    than one Joulescope is connected.  By default it matches any Joulescope
    (JS110, JS220 or JS320).  The :class:`~labgrid.driver.JoulescopeDriver`
    addresses the matched device through ``pyjoulescope_driver`` using the
    :attr:`serial` and :attr:`model` derived below.
    """

    def __attrs_post_init__(self):
        self.match["ID_VENDOR_ID"] = "16d0"
        super().__attrs_post_init__()

    def filter_match(self, device):
        return device.properties.get("ID_MODEL_ID") in JOULESCOPE_MODELS

    @property
    def serial(self):
        """The device serial number, identical to the pyjoulescope_driver path serial."""
        if self.device is not None:
            return self.device.properties.get("ID_SERIAL_SHORT")
        return None

    @property
    def model(self):
        """The device model, e.g. ``js320``, derived from the USB product id."""
        if self.device is not None:
            return JOULESCOPE_MODELS.get(self.device.properties.get("ID_MODEL_ID"))
        return None
