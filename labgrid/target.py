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
        for res in self.resources:
            if isinstance(res, cls):
                return res
        return None

    def get_driver(self, cls):
        """
        Helper function to get a driver of the target.
        Returns the first valid driver found, otherwise None.

        Arguments:
        cls -- driver-class to return as a resource
        """
        for drv in self.drivers:
            if isinstance(drv, cls):
                return drv
        return None
