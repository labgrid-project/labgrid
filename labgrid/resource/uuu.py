import attr

from ..factory import target_factory
from .common import Resource, NetworkResource


@target_factory.reg_resource
@attr.s(eq=False)
class UUU(Resource):
    """Describes a uuu resource which is available on the exporter."""
    def _convert(value):
        if isinstance(value, str):
            return [value]
        elif isinstance(value, list):
            return value
        else:
            raise Exception(f"{value} is neither a string nor a list")

    usb_otg_path = attr.ib(converter=_convert)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.usb_otg_path is None:
            raise ValueError("UUU must be configured with a usb_otg_path")


@target_factory.reg_resource
@attr.s(eq=False)
class NetworkUUU(NetworkResource, UUU):
    """A NetworkUUU could let you specify any host which connected with a uuu device."""
    pass
