import attr

from ..factory import target_factory
from .common import Resource


@attr.s(eq=False)
class BaseProvider(Resource):
    internal = attr.ib(validator=attr.validators.instance_of(str))
    external = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.host = "localhost"
        super().__attrs_post_init__()


@target_factory.reg_resource
@attr.s(eq=False)
class TFTPProvider(BaseProvider):
    pass


@target_factory.reg_resource
@attr.s(eq=False)
class NFSProvider(Resource):
    def __attrs_post_init__(self):
        self.host = "localhost"
        super().__attrs_post_init__()


@target_factory.reg_resource
@attr.s(eq=False)
class HTTPProvider(BaseProvider):
    pass
