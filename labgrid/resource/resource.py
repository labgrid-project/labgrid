import abc

class Resource(abc.ABC):
    def __init__ (self, target, upper):
        self.target.resources.append(upper)

    def on():
        raise NotImplementedError

    def off():
        raise NotImplementedError

    def reset():
        raise NotImplementedError

    def read():
        raise NotImplementedError

    def write():
        raise NotImplementedError

