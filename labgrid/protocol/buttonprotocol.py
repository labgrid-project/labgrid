import abc


class ButtonProtocol(abc.ABC):
    """Abstract class providing the ButtonProtocol interface"""

    @abc.abstractmethod
    def press(self):
        """Implementations should "press and hold" the button."""
        raise NotImplementedError

    @abc.abstractmethod
    def release(self):
        """Implementations should "release" the button"""
        raise NotImplementedError

    @abc.abstractmethod
    def press_for(self, time: float):
        """Implementations should "press" the button for time seconds and then "release" the button again"""
        raise NotImplementedError

    @abc.abstractmethod
    def get(self):
        """Implementations should return the status of the button"""
        raise NotImplementedError
