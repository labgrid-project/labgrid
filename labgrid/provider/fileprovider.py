import abc


class FileProvider(abc.ABC):
    """Abstract class for the FileProvider"""

    @abc.abstractmethod
    def get(self, name: str) -> dict:
        """
        Get a dictionary of target paths to local paths for a given name.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def list(self):
        """
        Get a list of names.
        """
        raise NotImplementedError
