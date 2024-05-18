import abc


class BootstrapProtocol(abc.ABC):
    @abc.abstractmethod
    def load(self, filename: str, phase=None):
        """Load a file into the DUT

        Args:
            filename (str): Filename to load
            phase (str): Loading phase, e.g. 'bl1'
        """
        raise NotImplementedError
