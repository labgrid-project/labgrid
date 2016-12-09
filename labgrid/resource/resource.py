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

@attr.s
class InfoResource(abc.ABC):

    @abc.abstractmethod
    def get(data: str):
        raise NotImplementedError
