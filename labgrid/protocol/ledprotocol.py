import abc

class LedProtocol(abc.ABC):

    """just write the brightness and check for errors"""
    @abc.abstractmethod
    def write_brightness(self, name, val):
        raise NotImplementedError

    """retrieve the current brightness """
    @abc.abstractmethod
    def get_brightness(self, name):
        raise NotImplementedError

    """set the brightness, read back and compare"""
    @abc.abstractmethod
    def set_brightness(self, name, val):
        raise NotImplementedError
