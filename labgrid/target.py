import attr
from .driver.exception import NoResourceError


@attr.s
class Target:
    name = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.resources = []  #pylint: disable=attribute-defined-outside-init
        self.drivers = []  #pylint: disable=attribute-defined-outside-init

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

    def add_resource(self, res):
        """
        Helper function to add a resource of the target.

        Arguments:
        res - resource to be added
        """
        self.resources.append(res)

    def rm_resource(self, res):
        """
        Helper function to remove a resource of the target.

        Arguments:
        res - resource to be removed
        """
        try:
            self.resources.remove(res)
        except ValueError:
            raise NoResourceError(
                "Can't remove resource, not part of the target"
            )

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

    def add_driver(self, drv):
        """
        Helper function to add a driver of the target.

        Arguments:
        drv - drvier to be added
        """
        self.drivers.append(drv)

    def cleanup(self):
        """Clean up conntected drivers and resources in reversed order"""
        for drv in reversed(self.drivers):
            if hasattr(drv, 'cleanup') and callable(getattr(drv, 'cleanup')):
                drv.cleanup()
        for res in reversed(self.resources):
            if hasattr(res, 'cleanup') and callable(getattr(res, 'cleanup')):
                res.cleanup()
