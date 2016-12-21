import abc


class MMIOProtocol(abc.ABC):
    @abc.abstractmethod
    def read(self, address: int, size: int, count: int) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    def write(self, address: int, size: int, data: bytes) -> None:
        raise NotImplementedError
