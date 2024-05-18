import abc


class ResetProtocol(abc.ABC):
    @abc.abstractmethod
    def reset(self):
        raise NotImplementedError

    @abc.abstractmethod
    def set_reset_enable(self, enable, mode):
        """Enable / disable the reset line

        Args:
            enable (bool): True to assert reset, False to de-assert reset
            mode (str): Reset mode to use, e.g. 'cold' for a cold reset which
                resets the whole board / power suppy; 'warm' for a warm reset
                which just resets the AP
        """
        raise NotImplementedError
