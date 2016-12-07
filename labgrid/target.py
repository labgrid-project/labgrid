import attr

@attr.s
class Target(object):
    name = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.resources = []
        self.drivers = []

    def get_resource(self, cls):
        for r in self.resources:
            if isinstance(r, cls):
                return r

    def get_driver(self, cls):
        for d in self.drivers:
            if isinstance(d, cls):
                return d
