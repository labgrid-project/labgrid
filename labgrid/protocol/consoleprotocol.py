import abc
import attr

@attr.s
class ConsoleProtocol(abc.ABC):
    """Abstract class for the ConsoleProtocol"""

    @abc.abstractmethod
    def run(self, command: str):
        """
        Run a command.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def login(self):
        """
        Login to device.
        """
        raise NotImplementedError
