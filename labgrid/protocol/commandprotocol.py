import abc


class CommandProtocol(abc.ABC):
    """Abstract class for the CommandProtocol"""

    @abc.abstractmethod
    def run(self, command: str):
        """
        Run a command
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run_check(self, command: str):
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
    def wait_for(self):
        """
        Wait for a shell command to return with the specified output
        """
        raise NotImplementedError

    @abc.abstractmethod
    def poll_until_success(self):
        """
        Repeatedly call a shell command until it succeeds
        """
        raise NotImplementedError
