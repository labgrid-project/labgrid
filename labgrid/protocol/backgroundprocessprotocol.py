import abc


class BackgroundProcessProtocol(abc.ABC):
    """
    Abstract class providing the BackgroundProcessProtocol interface. It allows running commands
    as background processes. Running multiple commands concurrently may work depending on the
    driver.

    Example usage:

    >>> from labgrid.util.timeout import Timeout
    >>> with Timeout(300.0) as timeout:
    >>>     process = driver.run_as_background_process('dd if=/dev/random bs=1M count=100')
    >>>     while driver.poll_background_process(process) is None and not timeout.expired:
    >>>         time.sleep(min(timeout.remaining, 1.0))
    >>>         stdout, stderr = driver.read_from_background_process(process, timeout=timeout.remaining)
    >>>         # do something else
    >>> exitcode = driver.poll_background_process(process)
    """

    @abc.abstractmethod
    def run_as_background_process(self, command):
        """
        Runs the given `command` as a background process and immediately return a process handle.
        Raises ExecutionError if the maximum number of allowed concurrent processes is exceeded.

        Args:
            command (str): the command to run in background

        Returns:
            process handle, type implementation defined
        """
        raise NotImplementedError

    @abc.abstractmethod
    def read_from_background_process(self, process, *, timeout=0):
        """
        Read stdout/stderr of background process until timeout. For timeout=0 (default) the call
        won't block and will return stdout/stderr until current EOF. For timeout=None the call
        will block until the process has terminated. Returns a tuple (stdout, stderr).
        Raises ExecutionError if process is not known.

        Args:
            process: process handle, type implementation defined
            timeout (int or None): will block until timeout is exceeded or process terminates,
                                   timeout=0 returns immediately (default), timeout=None blocks
                                   until process terminates

        Returns:
            (stdout (str), stderr (str))
        """
        raise NotImplementedError

    @abc.abstractmethod
    def poll_background_process(self, process):
        """
        Check if background process has terminated. Returns exitcode if process has terminated
        otherwise None. Raises ExecutionError if process is not known.

        Args:
            process: process handle, type implementation defined

        Returns:
            exit code if process terminated otherwise None
        """
        raise NotImplementedError
