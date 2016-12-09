import abc


class PowerProcotol(abc.ABC):
    @abc.abstractmethod
    def on(self):
        raise NotImplementedError

    @abc.abstractmethod
    def off(self):
        raise NotImplementedError

    @abc.abstractmethod
    def reset(self):
        raise NotImplementedError
