import abc


class VideoProtocol(abc.ABC):
    @abc.abstractmethod
    def get_qualities(self):
        raise NotImplementedError

    @abc.abstractmethod
    def stream(self, quality_hint=None):
        raise NotImplementedError

    @abc.abstractmethod
    def screenshot(self, filename):
        raise NotImplementedError
