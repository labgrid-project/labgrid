import pexpect
from ..protocol import ConsoleProtocol
from .exceptions import NoValidDriverError


class PtxExpect(pexpect.spawn):
    """labgrid Wrapper of the pexpect module.

    This class provides pexpect functionality for the ConsoleProtocol classes.
    driver: ConsoleProtocol object to be passed in
    """
    def __init__(self, driver, logfile=None, timeout=None, cwd=None):
        if not isinstance(driver, ConsoleProtocol):
            raise NoValidDriverError("driver is not a ConsoleProtocol driver")
        self.driver = driver
        self.logfile=logfile
        self.linesep = b"\n"
        pexpect.spawn.__init__(
            self, None,
            timeout=timeout,
            cwd=cwd,
            logfile=self.logfile,
        )
    def send(self, s):
        "Write to serial, return number of bytes written"
        s = self._coerce_send_string(s)
        self._log(s, 'send')

        b = s
        return self.driver.write(b)

    def read_nonblocking(self, size=1, timeout=0):
        """ Pexpects needs a nonblocking read function, simply use pyserial with a timeout of 0"""
        return self.driver.read(size=size,timeout=timeout)
