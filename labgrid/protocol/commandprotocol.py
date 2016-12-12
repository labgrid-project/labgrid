import abc


class CommandProtocol(abc.ABC):
    """Abstract class for the CommandProtocol"""

    @abc.abstractmethod
    def run(self, data: int):
        """
        Run a command
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_status(self):
        """
        Get status of the ShellDriver
        """
        raise NotImplementedError
