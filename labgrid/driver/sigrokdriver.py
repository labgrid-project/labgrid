import os.path
import re
import subprocess
import shutil
import tempfile
import time
import uuid
import csv

from time import sleep

import attr

from ..factory import target_factory
from ..protocol import PowerProtocol
from ..resource.remote import NetworkSigrokUSBDevice, NetworkSigrokUSBSerialDevice
from ..resource.udev import SigrokUSBDevice, SigrokUSBSerialDevice
from ..resource.sigrok import SigrokDevice
from ..step import step
from ..util.helper import processwrapper
from .common import Driver, check_file
from .exception import ExecutionError
from .powerdriver import PowerResetMixin
from ..util import Timeout


@attr.s(eq=False)
class SigrokCommon(Driver):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool(
                'sigrok-cli'
            ) or 'sigrok-cli'
        else:
            self.tool = 'sigrok-cli'
        self._running = False

    def _create_tmpdir(self):
        if isinstance(self.sigrok, NetworkSigrokUSBDevice):
            self._tmpdir = f'/tmp/labgrid-sigrok-{uuid.uuid1()}'
            command = self.sigrok.command_prefix + [
                'mkdir', '-p', self._tmpdir
            ]
            self.logger.debug("Tmpdir command: %s", command)
            subprocess.call(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.logger.debug("Created tmpdir: %s", self._tmpdir)
            self._local_tmpdir = tempfile.mkdtemp(prefix="labgrid-sigrok-")
            self.logger.debug("Created local tmpdir: %s", self._local_tmpdir)
        else:
            self._tmpdir = tempfile.mkdtemp(prefix="labgrid-sigrok-")
            self.logger.debug("created tmpdir: %s", self._tmpdir)

    def _delete_tmpdir(self):
        if isinstance(self.sigrok, NetworkSigrokUSBDevice):
            command = self.sigrok.command_prefix + [
                'rm', '-r', self._tmpdir
            ]
            self.logger.debug("Tmpdir command: %s", command)
            subprocess.call(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            shutil.rmtree(self._local_tmpdir)
        else:
            shutil.rmtree(self._tmpdir)

    def on_activate(self):
        self._create_tmpdir()

    def on_deactivate(self):
        self._delete_tmpdir()

    def _get_sigrok_prefix(self):
        prefix = [self.tool]
        if isinstance(self.sigrok, (NetworkSigrokUSBDevice, SigrokUSBDevice)):
            prefix += ["-d", f"{self.sigrok.driver}:conn={self.sigrok.busnum}.{self.sigrok.devnum}"]
        elif isinstance(self.sigrok, (NetworkSigrokUSBSerialDevice, SigrokUSBSerialDevice)):
            prefix += ["-d", f"{self.sigrok.driver}:conn={self.sigrok.path}"]
        else:
            prefix += ["-d", self.sigrok.driver]
        if self.sigrok.channels:
            prefix += ["-C", self.sigrok.channels]
        if self.sigrok.channel_group:
            prefix += ["-g", self.sigrok.channel_group]
        return self.sigrok.command_prefix + prefix

    @Driver.check_active
    @step(title='call_with_driver', args=['args'])
    def _call_with_driver(self, *args):
        combined = self._get_sigrok_prefix() + list(args)
        self.logger.debug("Combined command: %s", " ".join(combined))
        self._process = subprocess.Popen(
            combined,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    @Driver.check_active
    @step(title='call_with_driver_blocking', args=['args'])
    def _call_with_driver_blocking(self, *args, log_output=False):
        combined = self._get_sigrok_prefix() + list(args)
        self.logger.debug("Combined command: %s", " ".join(combined))
        process = subprocess.Popen(
            combined,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        if log_output:
            self.logger.debug("stdout: %s", stdout)
            self.logger.debug("stderr: %s", stderr)
        if process.returncode != 0:
            raise OSError
        return stdout, stderr


    @Driver.check_active
    @step(title='call', args=['args'])
    def _call(self, *args):
        combined = self.sigrok.command_prefix + [self.tool]
        if self.sigrok.channels:
            combined += ["-C", self.sigrok.channels]
        if self.sigrok.channel_group:
            combined += ["-g", self.sigrok.channel_group]
        combined += list(args)
        self.logger.debug("Combined command: %s", combined)
        self._process = subprocess.Popen(
            combined,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )


@target_factory.reg_driver
@attr.s(eq=False)
class SigrokDriver(SigrokCommon):
    """The SigrokDriver uses sigrok-cli to record samples and expose them as python dictionaries.

    Args:
        bindings (dict): driver to use with sigrok
    """
    bindings = {
        "sigrok": {SigrokUSBDevice, NetworkSigrokUSBDevice, SigrokDevice},
    }

    @Driver.check_active
    def capture(self, filename, samplerate="200k"):
        """
        Starts to capture samples, in the background.

        Args:
            filename: the path to the file where the capture is saved.
            samplerate: the sample-rate of the capture

        Raises:
            RuntimeError() if a capture is already running.
        """
        if self._running:
            raise RuntimeError("capture is already running")

        self._filename = filename
        self._basename = os.path.basename(self._filename)
        self.logger.debug(
            "Saving to: %s with basename: %s", self._filename, self._basename
        )
        cmd = [
            "-l", "4", "--config", f"samplerate={samplerate}",
            "--continuous", "-o"
        ]
        filename = os.path.join(self._tmpdir, self._basename)
        cmd.append(filename)
        self._call_with_driver(*cmd)

        args = self.sigrok.command_prefix + ['test', '-e', filename]

        while subprocess.call(args):
            # in case the sigrok-cli call fails, this would wait forever.
            # to avoid this, we also check the spawned sigrok process
            if self._process.poll() is not None:
                ret = self._process.returncode
                if ret != 0:
                    stdout, stderr = self._process.communicate()
                    self.logger.debug("sigrok-cli call terminated prematurely with non-zero return-code")
                    self.logger.debug("stdout: %s", stdout)
                    self.logger.debug("stderr: %s", stderr)
                    raise ExecutionError(f"sigrok-cli call terminated prematurely with return-code '{ret}'.")
            sleep(0.1)

        self._running = True

    @Driver.check_active
    def capture_for_time(self, filename, time_ms, samplerate="200k"):
        """
        Captures samples for a specified time (ms).

        Blocks while capturing.

        Args:
            filename: the path to the file where the capture is saved.
            time: time (in ms) for capture duration
            samplerate: the sample-rate of the capture

        Returns:
            The capture as a list containing dict's with fields "Time"
            and the channel names

        Raises:
            OSError() if the subprocess returned with non-zero return-code
        """
        return self._capture_blocking(filename, ["--time", str(time_ms)], samplerate)

    @Driver.check_active
    def capture_samples(self, filename, samples, samplerate="200k"):
        """
        Captures a specified number of samples.

        Blocks while capturing.

        Args:
            filename: the path to the file where the capture is saved.
            samples: number of samples to capture
            samplerate: the sample-rate of the capture

        Returns:
            The capture as a list containing dict's with fields "Time"
            and the channel names
        """
        return self._capture_blocking(filename, ["--samples", str(samples)], samplerate)

    @Driver.check_active
    def stop(self):
        """
        Stops the capture and returns recorded samples.

        Note that this method might block for several seconds because it needs
        to wait for output, parse the capture file and prepare the list
        containing the samples.

        Returns:
            The capture as a list containing dict's with fields "Time"
            and the channel names

        Raises:
            RuntimeError() if capture has not been started
        """
        if not self._running:
            raise RuntimeError("no capture started yet")
        self._running = False

        csv_filename = f'{os.path.splitext(self._basename)[0]}.csv'

        # sigrok-cli can be quit through any keypress
        stdout, stderr = self._process.communicate(input="q")
        self.logger.debug("stdout: %s", stdout)
        self.logger.debug("stderr: %s", stderr)

        self._convert_sr_csv(os.path.join(self._tmpdir, self._basename),
                             os.path.join(self._tmpdir, csv_filename))
        self._transfer_tmp_file(csv_filename)
        return self._process_csv(csv_filename)

    def _capture_blocking(self, filename, capture_args, samplerate):
        self._filename = filename
        self._basename = os.path.basename(self._filename)
        csv_filename = f'{os.path.splitext(self._basename)[0]}.csv'
        self.logger.debug(
            "Saving to: %s with basename: %s", self._filename, self._basename
        )
        cmd = [
            "-l", "4", "--config", f"samplerate={samplerate}",
            *capture_args, "-o"
        ]
        filename = os.path.join(self._tmpdir, self._basename)
        cmd.append(filename)
        self._call_with_driver_blocking(*cmd, log_output=True)

        args = self.sigrok.command_prefix + ['test', '-e', filename]

        while subprocess.call(args):
            sleep(0.1)

        self._convert_sr_csv(os.path.join(self._tmpdir, self._basename),
                             os.path.join(self._tmpdir, csv_filename))
        self._transfer_tmp_file(csv_filename)
        return self._process_csv(csv_filename)

    def _convert_sr_csv(self, file_path_sr, file_path_scv):
        cmd = [
            '-i',
            file_path_sr, '-O', 'csv:time=true', '-o',
            file_path_scv
        ]
        self._call(*cmd)
        stdout, stderr = self._process.communicate()
        self.logger.debug("stdout: %s", stdout)
        self.logger.debug("stderr: %s", stderr)


    def _transfer_tmp_file(self, csv_filename):
        if isinstance(self.sigrok, NetworkSigrokUSBDevice):
            sr_remote_path = os.path.join(self._tmpdir, self._basename)
            sr_local_path = os.path.abspath(self._filename)
            csv_remote_path = os.path.join(self._tmpdir, csv_filename)
            csv_local_path = os.path.join(self._local_tmpdir, csv_filename)
            self.logger.debug(
                "Transferring sigrok capture file from remote path '%s' to local path '%s'",
                sr_remote_path,
                sr_local_path
            )
            # TODO: use NetworkResource ssh base options here too
            ret = subprocess.run([
                    'scp',
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "StrictHostKeyChecking=no",
                    f'{self.sigrok.host}:{sr_remote_path}',
                    sr_local_path,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            if ret.returncode != 0:
                self.logger.error(
                    "Transfer Sigrok capture file failed with return-code '%i : %s'",
                    ret.returncode,
                    ret.stdout.decode()
                )
                raise ExecutionError(
                    f"Transfer Sigrok Capture file failed with return-code '{ret.returncode}'",
                    stdout=ret.stdout.decode().split("\n")
                )

            # get csv from remote host
            self.logger.debug(
                "Transferring CSV file from remote path '%s' to local path '%s'",
                csv_remote_path,
                csv_local_path
            )
            # TODO: use NetworkResource ssh base options here too
            ret = subprocess.run([
                    'scp',
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "StrictHostKeyChecking=no",
                    f'{self.sigrok.host}:{csv_remote_path}',
                    csv_local_path
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
            if ret.returncode != 0:
                self.logger.error(
                    "Transfer Sigrok CSV file failed with return-code '%i : %s'",
                    ret.returncode,
                    ret.stdout.decode()
                )
                raise ExecutionError(
                    f"Transfer Sigrok CSV file failed with return-code '{ret.returncode}'",
                    stdout=ret.stdout.decode().split("\n")
                )
        else:
            shutil.copyfile(
                os.path.join(self._tmpdir, self._basename), self._filename
            )

    def _process_csv(self, csv_filename):
        fnames = ['time']
        fnames.extend(self.sigrok.channels.split(','))

        if isinstance(self.sigrok, NetworkSigrokUSBDevice):
            with open(os.path.join(self._local_tmpdir,
                                   csv_filename)) as csv_file:
                # skip first 5 lines of the csv output, contains metadata and fieldnames
                for _ in range(0, 5):
                    next(csv_file)
                return list(csv.DictReader(csv_file, fieldnames=fnames))
        else:
            with open(os.path.join(self._tmpdir, csv_filename)) as csv_file:
                # skip first 5 lines of the csv output, contains metadata and fieldnames
                for _ in range(0, 5):
                    next(csv_file)
                return list(csv.DictReader(csv_file, fieldnames=fnames))

    @Driver.check_active
    def analyze(self, args, filename=None):
        """
        Analyzes captured data through `sigrok-cli`'s command line interface

        Args:
            args: args to `sigrok-cli`

        Returns:
            A dictionary containing the matched groups.
        """
        annotation_regex = re.compile(r'(?P<startnum>\d+)-(?P<endnum>\d+) (?P<decoder>[\w\-]+): (?P<annotation>[\w\-]+): (?P<data>".*)')  # pylint: disable=line-too-long
        if not filename and self._filename:
            filename = os.path.join(self._tmpdir, self._basename)
        else:
            filename = os.path.abspath(filename)
        check_file(filename, command_prefix=self.sigrok.command_prefix)
        args.insert(0, filename)
        if isinstance(args, str):
            args = args.split(" ")
        args.insert(0, '-i')
        args.append("--protocol-decoder-samplenum")
        args.append("-l")
        args.append("4")
        combined = self._get_sigrok_prefix() + args
        output = subprocess.check_output(combined)
        return [
            match.groupdict()
            for match in re.finditer(annotation_regex, output.decode("utf-8"))
        ]


@target_factory.reg_driver
@attr.s(eq=False)
class SigrokPowerDriver(SigrokCommon, PowerResetMixin, PowerProtocol):
    """The SigrokPowerDriverDriver uses sigrok-cli to control a PSU and collect
    measurements.

    Args:
        bindings (dict): driver to use with sigrok
    """
    bindings = {
        "sigrok": {SigrokUSBSerialDevice, NetworkSigrokUSBSerialDevice},
    }
    delay = attr.ib(default=3.0, validator=attr.validators.instance_of(float))
    max_voltage = attr.ib(
        default=None,
        converter=attr.converters.optional(float),
        validator=attr.validators.optional(attr.validators.instance_of(float)),
    )
    max_current = attr.ib(
        default=None,
        converter=attr.converters.optional(float),
        validator=attr.validators.optional(attr.validators.instance_of(float)),
    )

    @Driver.check_active
    @step()
    def on(self):
        processwrapper.check_output(
            self._get_sigrok_prefix() + ["--config", "enabled=yes", "--set"]
        )

    @Driver.check_active
    @step()
    def off(self):
        processwrapper.check_output(
            self._get_sigrok_prefix() + ["--config", "enabled=no", "--set"]
        )

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    @step(args=["value"])
    def set_voltage_target(self, value):
        if self.max_voltage is not None and value > self.max_voltage:
            raise ValueError(
                f"Requested voltage target({value}) is higher than configured maximum ({self.max_voltage})")  # pylint: disable=line-too-long
        processwrapper.check_output(
            self._get_sigrok_prefix() + ["--config", f"voltage_target={value:f}", "--set"]
        )

    @Driver.check_active
    @step(args=["value"])
    def set_current_limit(self, value):
        if self.max_current is not None and value > self.max_current:
            raise ValueError(
                f"Requested current limit ({value}) is higher than configured maximum ({self.max_current})")  # pylint: disable=line-too-long
        processwrapper.check_output(
            self._get_sigrok_prefix() + ["--config", f"current_limit={value:f}", "--set"]
        )

    @Driver.check_active
    @step(result=True)
    def get(self):
        out = processwrapper.check_output(
            self._get_sigrok_prefix() + ["--get", "enabled"]
        )
        if out == b'true':
            return True
        elif out == b'false':
            return False

        raise ExecutionError(f"Unkown enable status {out}")

    @Driver.check_active
    @step(result=True)
    def measure(self):
        out = processwrapper.check_output(
            self._get_sigrok_prefix() + ["--show"]
        )
        res = {}
        for line in out.splitlines():
            line = line.strip()
            if b':' not in line:
                continue
            k, v = line.split(b':', 1)
            if k == b'voltage':
                res['voltage'] = float(v)
            elif k == b'current':
                res['current'] = float(v)
        if len(res) != 2:
            raise ExecutionError(f"Cannot parse --show output {out}")
        return res

@target_factory.reg_driver
@attr.s(eq=False)
class SigrokDmmDriver(SigrokCommon):
    """
    This driver wraps around a single channel DMM controlled by sigrok.
    It has been tested with Unit-T UT61C and UT61B devices but probably also
    works with other single chnnel DMMs.

    This driver binds to a SigrokUsbDevice.
    Make sure to select the correct driver for your DMM there.

    Example usage:
    > resources:
    >   - SigrokUSBDevice:
    >       driver: uni-t-ut61c
    >       match:
    >         'ID_PATH': pci-0000:07:00.4-usb-0:2:1.0
    > drivers:
    >   - SigrokDmmDriver: {}

    Args:
        bindings (dict): driver to use with sigrok
    """

    bindings = {
        "sigrok": {SigrokUSBSerialDevice, NetworkSigrokUSBSerialDevice, SigrokUSBDevice, NetworkSigrokUSBDevice},
    }

    @Driver.check_active
    @step(result=True)
    def capture(self, samples, timeout=None):
        """
        Starts to read samples from the DMM.
        This method returns once sampling has been started. Sampling continues in the background.

        Note: We use subprocess.PIPE to buffer the samples.
        When this buffer is too small for the number of samples requested sampling may stall.

        Args:
            samples: Number of samples to obtain
            timeout: Timeout after which sampling should be stopped.
                     If None: timeout[s] = samples * 1s + 5s
                     If int: Timeout in [s]

        Raises:
            RuntimeError() if a capture is already running.
        """
        if self._running:
            raise RuntimeError("capture is already running")

        if not timeout:
            timeout = samples + 5.0

        args = f"-O csv --samples {samples}".split(" ")
        self._call_with_driver(*args)
        self._timeout = Timeout(timeout)
        self._running = True

    @Driver.check_active
    @step(result=True)
    def stop(self):
        """
        Waits for sigrok to complete and returns all samples obtained afterwards.
        This function blocks until either sigrok has terminated or the timeout has been reached.

        Returns:
            (unit_spec, [sample, ...])

        Raises:
            RuntimeError() if capture has not been started
            OSError() if the subprocess returned with non-zero return-code
        """
        if not self._running:
            raise RuntimeError("no capture started yet")
        while not self._timeout.expired:
            if self._process.poll() is not None:
                # process has finished. no need to wait for the timeout
                if self._process.returncode != 0:
                    raise OSError
                break
            time.sleep(0.1)
        else:
            # process did not finish in time
            self.logger.info("sigrok-cli did not finish in time, increase timeout?")
            self._process.kill()

        res = []
        unit = ""
        for line in self._process.stdout.readlines():
            line = line.strip()
            if b";" in line:
                # discard header information
                continue
            if not unit:
                # the first line after the header contains the unit information
                unit = line.decode()
            else:
                # all other lines are actual values
                res.append(float(line))
        _, stderr = self._process.communicate()
        self.logger.debug("stderr: %s", stderr)

        self._running = False
        return unit, res

    def on_activate(self):
        # This driver does not use self._tmpdir from SigrockCommon.
        # Overriding this function to inhibit the temp-dir creation.
        pass

    def on_deactivate(self):
        # This driver does not use self._tmpdir from SigrockCommon.
        # Overriding this function to inhibit the temp-dir creation.
        pass
