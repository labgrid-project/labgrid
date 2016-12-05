class Target(object):
    def __init__(self, name):
        self.name = name
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

    def __repr__(self):
        return 'Target({},{},{})'.format(self.name, self.resources,
                                           self.protocols)
