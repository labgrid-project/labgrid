import abc

from .digitalinputprotocol import DigitalInputProtocol


class DigitalOutputProtocol(DigitalInputProtocol):
    """Abstract class providing the DigitalOutputProtocol interface"""

    @abc.abstractmethod
    def set(self, status):
        """Implementations should set the status of the digital output"""
        raise NotImplementedError
