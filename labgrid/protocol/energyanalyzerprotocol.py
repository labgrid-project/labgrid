import abc


class EnergyAnalyzerProtocol(abc.ABC):
    """Protocol for energy analyzers such as the Joulescope.

    An energy analyzer continuously measures current, voltage and power and
    accumulates charge and energy.  Drivers implementing this protocol expose
    the latest statistics, an accumulation window (start/stop) for charge and
    energy, and high-rate sample capture to a file.
    """

    @abc.abstractmethod
    def get_statistics(self):
        """Return the latest measurement statistics as a dict.

        The returned dict contains ``current``, ``voltage`` and ``power``
        sub-dicts (each with ``avg``, ``std``, ``min`` and ``max`` keys) as
        well as the accumulated ``charge_C`` (Coulombs) and ``energy_J``
        (Joules).  Convenience values such as average current are read from
        this return value rather than via dedicated accessors.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def start(self):
        """Begin a charge/energy accumulation window."""
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self):
        """End the accumulation window started by :meth:`start`.

        Returns a dict with the accumulated ``energy_J`` (Joules),
        ``charge_C`` (Coulombs) and the ``duration_s`` (seconds) of the window.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def capture(self, filename, signals=None, duration=None, frequency=None):
        """Capture high-rate samples to a file for the given duration.

        ``frequency`` (in Hz) sets the device sample rate for the capture.  It
        is sticky: once set it remains in effect for subsequent captures on the
        same activated driver until changed again, rather than reverting to the
        device default.
        """
        raise NotImplementedError
