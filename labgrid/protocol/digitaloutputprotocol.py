import abc


class DigitalOutputProtocol(abc.ABC):
    """Abstract class providing the DigitalOutputProtocol interface"""

    @abc.abstractmethod
    def get(self):
        """Implementations should return the status of the digital output."""
        raise NotImplementedError

    @abc.abstractmethod
    def set(self, status):
        """Implementations should set the status of the digital output"""
        raise NotImplementedError
