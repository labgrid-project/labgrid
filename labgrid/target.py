import attr

@attr.s
class Target(object):
    name = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.resources = []
        self.protocols = []

    def get_resource(self, cls):
        result = []
        for r in self.resources:
            if isinstance(r, cls):
                result.append(r)
        return result

    def get_protocol(self, cls):
        result = []
        for p in self.protocols:
            if isinstance(p, cls):
                result.append(p)
        return result
