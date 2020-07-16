import abc


class BootCfgProtocol(abc.ABC):
    @abc.abstractmethod
    def usb(self):
        raise NotImplementedError

    @abc.abstractmethod
    def sd(self):
        raise NotImplementedError

    @abc.abstractmethod
    def emmc(self):
        raise NotImplementedError

    @abc.abstractmethod
    def qspi(self):
        raise NotImplementedError

