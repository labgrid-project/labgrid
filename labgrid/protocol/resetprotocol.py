import abc


class ResetProtocol(abc.ABC):
    @abc.abstractmethod
    def reset(self, mode=None):
        raise NotImplementedError
