import abc


class InfoProtocol(abc.ABC):
    """Abstract class providing the InfoProtocol interface"""

    @abc.abstractmethod
    def get_ip(self, interface: str = "eth0"):
        """Implementations should return the IP address for the supplied
        interface."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_hostname(self):
        """Implementations should return the hostname for the supplied
        interface."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_service_status(self, service):
        """Implementations should return the status of a service"""
        raise NotImplementedError
