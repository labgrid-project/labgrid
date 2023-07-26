import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class HttpDigitalOutput(Resource):
    """This resource describes a generic HTTP-controlled output pin.

    Args:
        url (str): URL to use for setting a new state
        body_asserted (str): Request body to send to assert the output
        body_deasserted (str): Request body to send to de-assert the output
        method (str): HTTP method to use instead of PUT (the default) to set a new state

        url_get (str): URL to use for getting the state
        body_get_asserted (str): Regular Expression that matches an asserted response body
        body_get_deasserted (str): Regular Expression that matches a de-asserted response body
    """

    url = attr.ib(validator=attr.validators.instance_of(str))
    body_asserted = attr.ib(validator=attr.validators.instance_of(str))
    body_deasserted = attr.ib(validator=attr.validators.instance_of(str))
    method = attr.ib(default="PUT", validator=attr.validators.instance_of(str))

    url_get = attr.ib(default="", validator=attr.validators.instance_of(str))
    body_get_asserted = attr.ib(
        default="", validator=attr.validators.instance_of(str)
    )
    body_get_deasserted = attr.ib(
        default="", validator=attr.validators.instance_of(str)
    )
