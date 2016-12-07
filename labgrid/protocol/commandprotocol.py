import abc
import attr

@attr.s
class CommandProtocol(abc.ABC):
    """Abstract class for the CommandProtocol"""

    @abc.abstractmethod
    def run(self):
        """
        Run a command
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_status(self):
        """
        Get status of the command
        """
        raise NotImplementedError
