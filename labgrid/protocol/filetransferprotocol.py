import abc


class FileTransferProtocol(abc.ABC):
    @abc.abstractmethod
    def put(self, filename: str):
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, filename: str):
        raise NotImplementedError
