import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class RTSPVideoStream(Resource):
    url = attr.ib(validator=attr.validators.instance_of(str))
