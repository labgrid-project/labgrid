import abc


class DigitalOutputProtocol(abc.ABC):
    """Abstract class providing the OneWireProtocol interface"""

    @abc.abstractmethod
    def get(self):
        """Implementations should return the status of the OneWirePort."""
        raise NotImplementedError

    @abc.abstractmethod
    def set(self, status):
        """Implementations should set the status of the OneWirePort"""
        raise NotImplementedError
