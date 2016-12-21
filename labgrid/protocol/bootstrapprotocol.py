import abc


class BootstrapProtocol(abc.ABC):
    @abc.abstractmethod
    def load(self, filename: str):
        raise NotImplementedError
