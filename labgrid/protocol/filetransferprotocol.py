import abc


class FileTransferProtocol(abc.ABC):
    @abc.abstractmethod
    def put(self, filename: str, remotepath: str):
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, filename: str, destination: str):
        raise NotImplementedError
