import attr

from ..factory import target_factory
from .common import Resource

@target_factory.reg_resource
@attr.s(eq=False)
class SigrokDevice(Resource):
    """The SigrokDevice describes an attached sigrok device with driver,
    channel mapping and channel group

    Args:
        driver (str): driver to use with sigrok
        channels (str): a sigrok channel mapping as described in the sigrok-cli man page
        channel_group (str): a sigrok channel group as described in the sigrok-cli man page
    """
    driver = attr.ib(default="demo")
    channels = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    channel_group = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
