import abc


class PowerProtocol(abc.ABC):
    @abc.abstractmethod
    def on(self):
        raise NotImplementedError

    @abc.abstractmethod
    def off(self):
        raise NotImplementedError

    @abc.abstractmethod
    def cycle(self):
        raise NotImplementedError
