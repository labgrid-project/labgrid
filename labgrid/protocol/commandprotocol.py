import abc


class CommandProcessProtocol(abc.ABC):
    """Abstract class for a running command"""

    def read(self, size=1, timeout=-1):
        """
        Reads up to size bytes from the remote process. If no output is
        available to read, will block up to timeout seconds waiting for output,
        then return any available (up to size bytes). If no output occurs
        before the timeout, a TIMEOUT exception is raised.

        If there is no more output because the process has exited, raises EOF

        If timeout is -1, the default timeout value will be used.

        This operates the same as read_nonblocking() from pexpect; You may want
        to look at the operations from the ReadMixIn class for more convenient
        methods of reading data from remote processes
        """
        raise NotImplementedError

    @abc.abstractmethod
    def write(self, data):
        """
        Write data to the process
        """
        raise NotImplementedError

    @abc.abstractmethod
    def poll(self):
        """
        Check if the process is alive. If the process is alive, None will be
        returned. If the process exited normally, the return code will be
        returned. If the process died from a signal, the negative value of the
        signal number will be returned.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self):
        """
        Stops the child process
        """
        raise NotImplementedError

    @abc.abstractmethod
    def expect(self, pattern, *, timeout=-1):
        """
        Seeks through the process output until a pattern is matched. See
        pexpect.spawn.expect()
        """
        raise NotImplementedError

    @abc.abstractmethod
    def wait(self):
        """
        Wait for the process to exit. Note that this may wait forever if the
        process generates output that is not read
        """
        raise NotImplementedError

    @abc.abstractmethod
    def sendcontrol(self, char):
        """
        Helper method that wraps write() with mnemonic access for sending
        control character to the child
        """
        raise NotImplementedError


class CommandProtocol(abc.ABC):
    """Abstract class for the CommandProtocol"""

    @abc.abstractmethod
    def run(self, command: str):
        """
        Run a command
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run_check(self, command: str):
        """
        Run a command, return str if successful, ExecutionError otherwise
        """
        raise NotImplementedError

    @abc.abstractmethod
    def start_process(self, cmd: str):
        """
        Start a new command process. Returns CommandProcessProtocol.

        If another command process is already running and the driver doesn't
        support multiple at the same time, CommandProcessBusy will be raised
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_status(self):
        """
        Get status of the Driver
        """
        raise NotImplementedError

    @abc.abstractmethod
    def wait_for(self):
        """
        Wait for a shell command to return with the specified output
        """
        raise NotImplementedError

    @abc.abstractmethod
    def poll_until_success(self):
        """
        Repeatedly call a shell command until it succeeds
        """
        raise NotImplementedError
