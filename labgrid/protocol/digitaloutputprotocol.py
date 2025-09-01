import abc
from .digitalinputprotocol import DigitalInputProtocol


class DigitalOutputProtocol(DigitalInputProtocol):
    """Abstract class providing the DigitalOutputProtocol interface.
    Implies that the set output can be read as well, so requires DigitalInputProtocol"""

    @abc.abstractmethod
    def set(self, status):
        """Implementations should set the status of the digital output"""
        raise NotImplementedError
