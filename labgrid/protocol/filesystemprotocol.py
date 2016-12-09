import abc


class FileSytemProtocol(abc.ABC):
    @abc.abstractmethod
    def upload(self, filename: str):
        raise NotImplementedError

    @abc.abstractmethod
    def download(self, filename: str):
        raise NotImplementedError
