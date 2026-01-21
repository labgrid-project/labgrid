import abc
from typing import Optional

from pexpect import EOF, TIMEOUT


class ConsoleProtocol(abc.ABC):
    """Abstract class for the ConsoleProtocol"""

    @abc.abstractmethod
    def read(self, size: int = 1, timeout: float = 0.0, max_size: Optional[int] = None):
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

    def expect(
        self,
        pattern: str | bytes | type[EOF] | type[TIMEOUT] | list[str | bytes | type[EOF] | type[TIMEOUT]],
        timeout: float = -1,
    ):
        raise NotImplementedError

    class Client(abc.ABC):
        @abc.abstractmethod
        def get_console_matches(self):
            raise NotImplementedError

        @abc.abstractmethod
        def notify_console_match(self, pattern, match):
            raise NotImplementedError
