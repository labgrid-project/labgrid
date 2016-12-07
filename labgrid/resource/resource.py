import abc
import attr

@attr.s
class IOResource(abc.ABC):
    @abc.abstractmethod
    def read():
        raise NotImplementedError

    @abc.abstractmethod
    def write():
        raise NotImplementedError

