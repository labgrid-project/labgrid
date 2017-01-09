import abc


class InfoProtocol(abc.ABC):
    @abc.abstractmethod
    def get_ip(self, interface: str='eth0'):
        raise NotImplementedError

    @abc.abstractmethod
    def get_hostname(self):
        raise NotImplementedError
