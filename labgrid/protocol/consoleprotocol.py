import pexpect
import attr
import abc

@attr.s
class ConsoleProtocol(abc.ABC):

    @abc.abstractmethod
    def run(self, command: str):
        raise NotImplementedError
