import abc


class ConsoleProtocol(abc.ABC):
    """Abstract class for the ConsoleProtocol"""

    @abc.abstractmethod
    def read(self):
        """
        Read data from underlying port
        """
        raise NotImplementedError

    @abc.abstractmethod
    def write(self, data: bytes):
        """
        Write data to underlying port
        """
        raise NotImplementedError

    def sendline(self, line: str):
        raise NotImplementedError

    def sendcontrol(self, char: str):
        raise NotImplementedError

    def expect(self, pattern: str):
        raise NotImplementedError

    class Client(abc.ABC):
        @abc.abstractmethod
        def get_console_matches(self):
            raise NotImplementedError

        @abc.abstractmethod
        def notify_console_match(self, pattern, match):
            raise NotImplementedError
