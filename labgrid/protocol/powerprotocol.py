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


class ProgrammablePowerProtocol(PowerProtocol):
    @abc.abstractmethod
    def show(self, index):
        raise NotImplementedError

    @abc.abstractmethod
    def voltage(self, index, voltage):
        raise NotImplementedError

    @abc.abstractmethod
    def amps(self, index, amps):
        raise NotImplementedError
