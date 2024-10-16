import abc


class ResetProtocol(abc.ABC):
    @abc.abstractmethod
    def reset(self):
        raise NotImplementedError
