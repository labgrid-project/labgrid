import abc


class FileSystemProtocol(abc.ABC):
    @abc.abstractmethod
    def read(self, filename: str):
        raise NotImplementedError

    @abc.abstractmethod
    def write(self, filename: str, data: bytes, append: bool):
        raise NotImplementedError
