import abc


class InfoProtocol(abc.ABC):
    """Abstract class providing the InfoProtocol interface"""

    @abc.abstractmethod
    def get_ip(self, interface: str='eth0'):
        """Implementations should return the IP-adress for the supplied
        interface."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_hostname(self):
        """Implementations should return the hostname for the supplied
        interface."""
        raise NotImplementedError

    @abc.abstractmethod
    def put_ssh_key(self, key: str):
        """Implementations should manage the upload of an SSH Key to the target"""
        raise NotImplementedError
