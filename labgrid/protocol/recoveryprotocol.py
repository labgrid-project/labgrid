import abc


class RecoveryProtocol(abc.ABC):
    """Abstract class providing the RecoveryProtocol interface"""

    @abc.abstractmethod
    def set_enable(self, status):
        """Implementations should set the status of the digital output

        Args:
            status (bool): True to enable recovery, False to disable
        """
        raise NotImplementedError
