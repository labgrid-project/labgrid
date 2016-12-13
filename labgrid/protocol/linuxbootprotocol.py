import attr
import abc


class LinuxBootProtocol(abc.ABC):
    @abc.abstractmethod
    def boot(self, name: str):
        raise NotImplementedError

    @abc.abstractmethod
    def await_boot(self):
        raise NotImplementedError
