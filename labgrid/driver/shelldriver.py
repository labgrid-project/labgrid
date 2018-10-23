# pylint: disable=no-member,missing-kwoa,unused-argument
"""The ShellDriver provides the CommandProtocol, ConsoleProtocol and
 InfoProtocol on top of a SerialPort."""
import io
import logging
import re
import time
import shlex
import attr
from pexpect import TIMEOUT
import xmodem

from ..factory import target_factory
from ..protocol import CommandProtocol, ConsoleProtocol, FileTransferProtocol
from ..step import step
from ..util import gen_marker
from .commandmixin import CommandMixin
from .common import Driver
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s(cmp=False)
class ShellDriver(CommandMixin, Driver, CommandProtocol, FileTransferProtocol):
    """ShellDriver - Driver to execute commands on the shell
    ShellDriver binds on top of a ConsoleProtocol.

    Args:
        prompt (regex): the shell prompt to detect
        login_prompt (regex): the login prompt to detect
        username (str): username to login with
        password (str): password to login with
        keyfile (str): keyfile to bind mount over users authorized keys
        login_timeout (int): optional, timeout for login prompt detection
    """
    bindings = {"console": ConsoleProtocol, }
    prompt = attr.ib(validator=attr.validators.instance_of(str))
    login_prompt = attr.ib(validator=attr.validators.instance_of(str))
    username = attr.ib(validator=attr.validators.instance_of(str))
    password = attr.ib(default="", validator=attr.validators.instance_of(str))
    keyfile = attr.ib(default="", validator=attr.validators.instance_of(str))
    login_timeout = attr.ib(default=60, validator=attr.validators.instance_of(int))
    console_ready = attr.ib(default="", validator=attr.validators.instance_of(str))
    await_login_timeout = attr.ib(default=2, validator=attr.validators.instance_of(int))


    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.re_vt100 = re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        )  # pylint: disable=attribute-defined-outside-init,anomalous-backslash-in-string
        self.logger = logging.getLogger("{}:{}".format(self, self.target))
        self._status = 0  # pylint: disable=attribute-defined-outside-init

        self._xmodem_cached_rx_cmd = ""
        self._xmodem_cached_sx_cmd = ""

    def on_activate(self):
        if self._status == 0:
            self._await_login()
            self._inject_run()
        if self.keyfile:
            self._put_ssh_key(self.keyfile)
        # Turn off Kernel Messages to the console
        self._run("dmesg -n 1")

    def on_deactivate(self):
        self._status = 0

    def _run(self, cmd, *, timeout=30.0, codec="utf-8", decodeerrors="strict"):
        """
        Runs the specified cmd on the shell and returns the output.

        Arguments:
        cmd - cmd to run on the shell
        """
        # FIXME: Handle pexpect Timeout
        self._check_prompt()
        marker = gen_marker()
        # hide marker from expect
        cmp_command = '''MARKER='{}''{}' run {}'''.format(
            marker[:4], marker[4:], shlex.quote(cmd)
        )
        self.console.sendline(cmp_command)
        _, _, match, _ = self.console.expect(r'{}(.*){}\s+(\d+)\s+{}'.format(
            marker, marker, self.prompt
        ), timeout=timeout)
        # Remove VT100 Codes, split by newline and remove surrounding newline
        data = self.re_vt100.sub('', match.group(1).decode(codec, decodeerrors)).split('\r\n')
        if data and not data[-1]:
            del data[-1]
        self.logger.debug("Received Data: %s", data)
        # Get exit code
        exitcode = int(match.group(2))
        return (data, [], exitcode)

    @Driver.check_active
    @step(args=['cmd'], result=True)
    def run(self, cmd, timeout=30.0, codec="utf-8", decodeerrors="strict"):
        return self._run(cmd, timeout=timeout, codec=codec, decodeerrors=decodeerrors)

    @step()
    def _await_login(self):
        """Awaits the login prompt and logs the user in"""

        start = time.time()

        expectations = [self.prompt, self.login_prompt, TIMEOUT]
        if self.console_ready != "":
            expectations.append(self.console_ready)

        # We call console.expect with a short timeout here to detect if the
        # console is idle, which results in a timeout without any changes to
        # the before property. So we store the last before value we've seen.
        # Because pexpect keeps any read data in it's buffer when a timeout
        # occours, we can't lose any data this way.
        last_before = b''

        while True:
            index, before, _, _ = self.console.expect(
                expectations,
                timeout=self.await_login_timeout
            )

            if index == 0:
                # we got a promt. no need for any further action to activate
                # this driver.
                self.status = 1
                break

            elif index == 1:
                # we need to login
                self.console.sendline(self.username)
                index, _, _, _ = self.console.expect([self.prompt, "Password: "], timeout=10)
                if index == 1:
                    if self.password:
                        self.console.sendline(self.password)
                        self.console.expect(self.prompt, timeout=5)
                    else:
                        raise Exception("Password entry needed but no password set")
                self._check_prompt()
                break

            elif index == 2:
                # expect hit a timeout while waiting for a match
                if before == last_before:
                    # we did not receive anything during
                    # self.await_login_timeout.
                    # let's assume the target is idle and we can safely issue a
                    # newline to check the state
                    self.console.sendline("")

            elif index == 3:
                # we have just activated a console here
                # lets start over again and see if login or prompt will appear
                # now.
                self.console.sendline("")

            last_before = before

            if time.time() > start + self.login_timeout:
                raise TIMEOUT("Timeout of {} seconds exceeded during waiting for login".format(self.login_timeout))  # pylint: disable=line-too-long

    @step()
    def get_status(self):
        """Returns the status of the shell-driver.
        0 means not connected/found, 1 means shell
        """
        return self._status

    def _check_prompt(self):
        """
        Internal function to check if we have a valid prompt
        """
        marker = gen_marker()
        # hide marker from expect
        self.console.sendline("echo '{}''{}'".format(marker[:4], marker[4:]))
        try:
            self.console.expect("{}".format(marker), timeout=2)
            self.console.expect(self.prompt, timeout=1)
            self._status = 1
        except TIMEOUT:
            self._status = 0
            raise

    def _inject_run(self):
        self.console.sendline(
            '''run() { echo -n "$MARKER"; sh -c "$@"; echo "$MARKER $?"; }'''
        )
        self.console.expect(self.prompt)

    @step(args=['keyfile_path'])
    def _put_ssh_key(self, keyfile_path):
        """Upload an SSH Key to a target"""
        regex = re.compile(
            r"""ssh-rsa # Only match RSA Keys
            \s+(?P<key>[a-zA-Z0-9/+=]+) # Match Keystring
            \s+(?P<comment>.*) # Match comment""", re.X
        )
        with open(keyfile_path) as keyfile:
            keyline = keyfile.readline()
            self.logger.debug("Read Keyline: %s", keyline)
            match = regex.match(keyline)
            if match:
                new_key = match.groupdict()
            else:
                raise IOError(
                    "Could not parse SSH-Key from file: {}".
                    format(keyfile)
                )
        self.logger.debug("Read Key: %s", new_key)
        auth_keys, _, read_keys = self._run("cat ~/.ssh/authorized_keys")
        self.logger.debug("Exitcode trying to read keys: %s, keys: %s", read_keys, auth_keys)
        result = []
        _, _, test_write = self._run("touch ~/.test")
        if read_keys == 0:
            for line in auth_keys:
                match = regex.match(line)
                if match:
                    match = match.groupdict()
                    self.logger.debug("Match dict: %s", match)
                    result.append(match)
            self.logger.debug("Complete result: %s", result)
            for key in result:
                self.logger.debug(
                    "Key, newkey: %s,%s", key['key'], new_key['key']
                )
                if key['key'] == new_key['key']:
                    self.logger.info("Key already on target")
                    return

        if test_write == 0 and read_keys == 0:
            self.logger.debug("Key not on target and writeable, concatenating...")
            self._run_check('echo "{}" >> ~/.ssh/authorized_keys'.format(keyline))
            self._run_check("rm ~/.test")
            return

        if test_write == 0:
            self.logger.debug("Key not on target, testing for .ssh directory")
            _, _, ssh_dir = self._run("[ -d ~/.ssh/ ]")
            if ssh_dir != 0:
                self.logger.debug("~/.ssh did not exist, creating")
                self._run("mkdir ~/.ssh/")
            self._run_check("chmod 700 ~/.ssh/")
            self.logger.debug("Creating ~/.ssh/authorized_keys")
            self._run_check('echo "{}" > ~/.ssh/authorized_keys'.format(keyline))
            self._run_check("rm ~/.test")
            return

        self.logger.debug("Key not on target and not writeable, using bind mount...")
        self._run_check('mkdir -m 700 /tmp/labgrid-ssh/')
        self._run("cp -a ~/.ssh/* /tmp/labgrid-ssh/")
        self._run_check('echo "{}" >> /tmp/labgrid-ssh/authorized_keys'.format(keyline))
        self._run_check('chmod 600 /tmp/labgrid-ssh/authorized_keys')
        out, err, exitcode = self._run('mount --bind /tmp/labgrid-ssh/ ~/.ssh/')
        if exitcode != 0:
            self.logger.warning("Could not bind mount ~/.ssh directory: %s %s", out, err)

    @Driver.check_active
    def put_ssh_key(self, keyfile_path):
        self._put_ssh_key(keyfile_path)

    def _xmodem_getc(self, size, timeout=10):
        """ called by the xmodem.XMODEM instance to read protocol data from the console """
        try:
            # use the underlying expect mechanism, which may have already accidentally read
            # something of the XMODEM protocol data into its internal buffers:
            xpct = self.console.expect(r'.{%d}' % size, timeout=timeout)
            s = xpct[2].group()
            self.logger.debug('XMODEM GETC(%d): read %r', size, s)
            return s
        except TIMEOUT:
            self.logger.debug('XMODEM GETC(%s): TIMEOUT after %d seconds', size, timeout)
            return None

    def _xmodem_putc(self, data, timeout=1):
        """ called by the xmodem.XMODEM instance to write protocol data to the console """
        # Note: we ignore the timeout because we cannot pass it through.
        self.logger.debug('XMODEM PUTC: %r', data)
        self.console.write(data)
        return len(data)

    def _start_xmodem_transfer(self, cmd):
        """
        Start transfer command and synchronize until start of XMODEM stream.

        We don't use _run() here because it expects a prompt, but we want to
        read from the console directly into our XMODEM instance instead.
        """

        marker = gen_marker()
        marked_cmd = "echo '{}''{}'; {}".format(marker[:4], marker[4:], cmd)
        self.console.sendline(marked_cmd)
        self.console.expect(marker, timeout=30)

    def _get_xmodem_rx_cmd(self, filename):
        """ Detect which XMODEM receive command can be used on the target, and cache the result. """
        if not self._xmodem_cached_rx_cmd:
            if self._run('which rx')[0]:
                # busybox rx
                self._xmodem_cached_rx_cmd = "rx '{filename}'"
            elif self._run('which lrz')[0]:
                # redirect stderr to prevent lrz from printing "ready to receive
                # $file", which will confuse the XMODEM instance
                self._xmodem_cached_rx_cmd = "lrz -X -y -c -b '{filename}' 2>/dev/null"
            else:
                raise ExecutionError('No XMODEM receiver (rx, lrz) available on target')

        # use the cached string template to make the full command with parameters
        return self._xmodem_cached_rx_cmd.format(filename=filename)

    def _get_xmodem_sx_cmd(self, filename):
        """ Detect which XMODEM send command can be used on the target, and cache the result. """
        if not self._xmodem_cached_sx_cmd:
            if self._run('which lsz')[0]:
                # redirect stderr to prevent lsz from printing "Give XMODEM receive
                # cmd now", which will confuse the XMODEM instance
                self._xmodem_cached_sx_cmd = "lsz -b -X -m 1200 -M 10 '{filename}' 2>/dev/null"
            else:
                raise ExecutionError('No XMODEM sender (lsz) available on target')

        # use the cached string template to make the full command with parameters
        return self._xmodem_cached_sx_cmd.format(filename=filename)

    @step(title='put_bytes', args=['remotefile'])
    def _put_bytes(self, buf: bytes, remotefile: str):
        # OK, a little explanation on what we're doing here:
        # XMODEM is a fairly simple, but also a fairly historic protocol. For example, all packets
        # carry exactly 128 bytes of payload, and if the file being sent is not a multiple of 128
        # bytes, the last packet will be padded by CPM's EOF, which is 0x1a. There is no file size
        # or anything in the protocol itself, so we'll have to take care of that and truncate the
        # file ourselves.

        def _target_cleanup(tmpfile):
            self._run("rm -f '{}'".format(tmpfile))

        stream = io.BytesIO(buf)

        # We first write to a temp file, which we'll `dd` onto the destination file later
        tmpfile = self._run_check('mktemp')
        if not tmpfile:
            raise ExecutionError('Could not make temporary file on target')
        tmpfile = tmpfile[0]

        try:
            rx_cmd = self._get_xmodem_rx_cmd(tmpfile)
            self.logger.debug('XMODEM receive command on target: %s', rx_cmd)
        except ExecutionError:
            _target_cleanup(tmpfile)
            raise

        self._start_xmodem_transfer(rx_cmd)

        modem = xmodem.XMODEM(self._xmodem_getc, self._xmodem_putc)
        ret = modem.send(stream)
        self.logger.debug('xmodem.send() returned %r', ret)

        self.console.expect(self.prompt, timeout=30)

        # truncate the file to get rid of CPMEOF padding
        dd_cmd = "dd if='{}' of='{}' bs=1 count={}".format(tmpfile, remotefile, len(buf))
        self.logger.debug('dd command: %s', dd_cmd)
        out, _, ret = self._run(dd_cmd)

        _target_cleanup(tmpfile)
        if ret != 0:
            raise ExecutionError('Could not truncate destination file: dd returned {}: {}'.
                                 format(ret, out))

    @Driver.check_active
    def put_bytes(self, buf: bytes, remotefile: str):
        """ Upload a file to the target.
        Will silently overwrite the remote file if it already exists.

        Args:
            buf (bytes): file contents
            remotefile (str): destination filename on the target

        Raises:
            IOError: if the provided localfile could not be found
            ExecutionError: if something else went wrong
        """
        return self._put_bytes(buf, remotefile)

    @step(title='put', args=['localfile', 'remotefile'])
    def _put(self, localfile: str, remotefile: str):
        with open(localfile, 'rb') as fh:
            buf = fh.read(None)
            self._put_bytes(buf, remotefile)

    @Driver.check_active
    def put(self, localfile: str, remotefile: str):
        """ Upload a file to the target.
        Will silently overwrite the remote file if it already exists.

        Args:
            localfile (str): source filename on the local machine
            remotefile (str): destination filename on the target

        Raises:
            IOError: if the provided localfile could not be found
            ExecutionError: if something else went wrong
        """
        self._put(localfile, remotefile)

    @step(title='get_bytes', args=['remotefile'])
    def _get_bytes(self, remotefile: str):
        buf = io.BytesIO()

        cmd = self._get_xmodem_sx_cmd(remotefile)
        self.logger.info('XMODEM send command on target: %s', cmd)

        # get file size to remove XMODEM's CPMEOF padding at the end of the last packet
        out, _, ret = self._run("stat '{}'".format(remotefile))
        match = re.search(r'Size:\s+(?P<size>\d+)', '\n'.join(out))
        if ret != 0 or not match or not match.group("size"):
            raise ExecutionError("Could not stat '{}' on target".format(remotefile))

        file_size = int(match.group('size'))
        self.logger.debug('file size on target is %d', file_size)

        self._start_xmodem_transfer(cmd)

        modem = xmodem.XMODEM(self._xmodem_getc, self._xmodem_putc)
        recvd_size = modem.recv(buf)
        self.logger.debug('xmodem.recv() returned %r', recvd_size)

        # remove CPMEOF (0x1a) padding
        if recvd_size < file_size:
            raise ExecutionError('Only received {} bytes of {} expected'.
                                 format(recvd_size, file_size))

        self.logger.debug('received %d bytes of payload', file_size)
        buf.truncate(file_size)

        self.console.expect(self.prompt, timeout=30)

        # return everything as bytes
        buf.seek(0)
        return buf.read()

    @Driver.check_active
    def get_bytes(self, remotefile: str):
        """ Download a file from the target.

        Args:
            remotefile (str): source filename on the target

        Returns:
            (bytes) file contents

        Raises:
            IOError: if localfile could be written
            ExecutionError: if something went wrong
        """
        return self._get_bytes(remotefile)

    @step(title='get', args=['remotefile', 'localfile'])
    def _get(self, remotefile: str, localfile: str):
        with open(localfile, 'wb') as fh:
            buf = self._get_bytes(remotefile)
            fh.write(buf)

    @Driver.check_active
    def get(self, remotefile: str, localfile: str):
        """ Download a file from the target.
        Will silently overwrite the local file if it already exists.

        Args:
            remotefile (str): source filename on the target
            localfile (str): destination filename on the local machine (can be relative)

        Raises:
            IOError: if localfile could be written
            ExecutionError: if something went wrong
        """
        self._get(remotefile, localfile)

    @step(title='run_script', args=['data', 'timeout'])
    def _run_script(self, data: bytes, timeout: int = 60):
        hardcoded_remote_file = '/tmp/labgrid-run-script'
        self._put_bytes(data, hardcoded_remote_file)
        self._run_check("chmod +x '{}'".format(hardcoded_remote_file))
        return self._run(hardcoded_remote_file, timeout=timeout)

    @Driver.check_active
    def run_script(self, data: bytes, timeout: int = 60):
        """ Upload a script to the target and run it.

        Args:
            data (bytes): script data
            timeout (int): timeout for the script to finish execution

        Returns:
            Tuple of (stdout: str, stderr: str, return_value: int)

        Raises:
            IOError: if the provided localfile could not be found
            ExecutionError: if something else went wrong
        """
        self._run_script(data, timeout)

    @step(title='run_script_file', args=['scriptfile', 'timeout', 'args'])
    def _run_script_file(self, scriptfile: str, *args, timeout: int = 60):
        hardcoded_remote_file = '/tmp/labgrid-run-script'
        self._put(scriptfile, hardcoded_remote_file)
        self._run_check("chmod +x '{}'".format(hardcoded_remote_file))

        shargs = [shlex.quote(a) for a in args]
        cmd = "{} {}".format(hardcoded_remote_file, ' '.join(shargs))
        return self._run(cmd, timeout=timeout)

    @Driver.check_active
    def run_script_file(self, scriptfile: str, *args, timeout: int = 60):
        """ Upload a script file to the target and run it.

        Args:
            scriptfile (str): source file on the local file system to upload to the target
            *args: (list of str): any arguments for the script as positional arguments
            timeout (int): timeout for the script to finish execution

        Returns:
            Tuple of (stdout: str, stderr: str, return_value: int)

        Raises:
            ExecutionError: if something went wrong
            IOError: if the provided localfile could not be found
        """
        self._run_script_file(scriptfile, *args, timeout=timeout)
