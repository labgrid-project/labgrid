import abc


class CommandProtocol(abc.ABC):
    """Abstract class for the CommandProtocol"""

    @abc.abstractmethod
    def run(self, command: str, *, timeout: int):
        """
        Run a command
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run_check(self, command: str, *, timeout: int):
        """
        Run a command, return str if succesful, ExecutionError otherwise
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_status(self):
        """
        Get status of the Driver
        """
        raise NotImplementedError

    @abc.abstractmethod
    def wait_for(self, command: str, pattern: str, *, timeout: int = 30, sleepduration: int = 1):
        """
        Wait for a shell command to return with the specified output
        """
        raise NotImplementedError

    @abc.abstractmethod
    def poll_until_success(self, command: str, *, expected: int = 0, tries: int = None,
                           timeout: int = 30, sleepduration: int = 1):
        """
        Poll a command until a specific exit code is detected.
        """
        raise NotImplementedError
