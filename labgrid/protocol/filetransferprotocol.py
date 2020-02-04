import abc


class FileTransferProtocol(abc.ABC):
    @abc.abstractmethod
    def put(self, local_file: str, remote_file: str):
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, remote_file: str, local_file: str):
        raise NotImplementedError
