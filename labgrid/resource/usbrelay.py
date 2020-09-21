import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class USBRelay(Resource):
    """This resource describes a usbrelay which is controlled by (https://github.com/darrylb123/usbrelay)

    Args:
        name (str): relay identification
        index (int) optional: index of the relay to switch (defaults to 1)
    """

    name = attr.ib(validator=attr.validators.instance_of(str))
    index = attr.ib(default=1, validator=attr.validators.instance_of(int))