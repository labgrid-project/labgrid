import abc


class DigitalInputProtocol(abc.ABC):
    """Abstract class providing the DigitalInputProtocol interface"""

    @abc.abstractmethod
    def get(self):
        """Implementations should return the status of the digital input."""
        raise NotImplementedError
