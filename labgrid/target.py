import attr

@attr.s
class Target(object):
    name = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.resources = [] #pylint: disable=attribute-defined-outside-init
        self.drivers = [] #pylint: disable=attribute-defined-outside-init

    def get_resource(self, cls):
        """
        Helper function to get a resource of the target.
        Returns the first valid resource found, otherwise None.

        Arguments:
        cls -- resource-class to return as a resource
        """
        for r in self.resources:
            if isinstance(r, cls):
                return r
        return None

    def get_driver(self, cls):
        """
        Helper function to get a driver of the target.
        Returns the first valid driver found, otherwise None.

        Arguments:
        cls -- driver-class to return as a resource
        """
        for d in self.drivers:
            if isinstance(d, cls):
                return d
        return None
