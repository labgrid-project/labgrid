import attr
from .resource import InfoResource


@attr.s
class NetworkResource(InfoResource):
    target = attr.ib()
    addresses = attr.ib(default={},
                        validator=attr.validators.instance_of(dict))
    hostname = attr.ib(default="", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        pass

    def get_if_addr(self, adr):
        """Returns the address for the specified interface"""
        return self.addresses[adr] #pylint: disable=unsubscriptable-object

    def get_hostname(self):
        """Returns the address for the specified interface"""
        return self.hostname #pylint: disable=unsubscriptable-object
