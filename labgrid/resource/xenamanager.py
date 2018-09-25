import attr

from ..factory import target_factory
from .common import Resource

@target_factory.reg_resource
@attr.s(cmp=False)
class XenaManager(Resource):
    """ Hostname/IP identifying the manageent address of the xena tester """
    hostname = attr.ib(validator=attr.validators.instance_of(str))
