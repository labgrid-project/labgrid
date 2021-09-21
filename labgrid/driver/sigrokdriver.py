# pylint: disable=no-member
import logging
import os.path
import re
import subprocess
import shutil
import signal
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
        self.log = logging.getLogger("SigrokDriver")
        self._running = False

    def _create_tmpdir(self):
        if isinstance(self.sigrok, NetworkSigrokUSBDevice):
            self._tmpdir = f'/tmp/labgrid-sigrok-{uuid.uuid1()}'
            command = self.sigrok.command_prefix + [
                'mkdir', '-p', self._tmpdir
            ]
            self.log.debug("Tmpdir command: %s", command)
            subprocess.call(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.log.debug("Created tmpdir: %s", self._tmpdir)
            self._local_tmpdir = tempfile.mkdtemp(prefix="labgrid-sigrok-")
            self.log.debug("Created local tmpdir: %s", self._local_tmpdir)
        else:
            self._tmpdir = tempfile.mkdtemp(prefix="labgrid-sigrok-")
            self.log.debug("created tmpdir: %s", self._tmpdir)

    def _delete_tmpdir(self):
        if isinstance(self.sigrok, NetworkSigrokUSBDevice):
            command = self.sigrok.command_prefix + [
                'rm', '-r', self._tmpdir
            ]
            self.log.debug("Tmpdir command: %s", command)
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
        return self.sigrok.command_prefix + prefix

    @Driver.check_active
    @step(title='call', args=['args'])
    def _call_with_driver(self, *args):
        combined = self._get_sigrok_prefix() + list(args)
        self.log.debug("Combined command: %s", " ".join(combined))
        self._process = subprocess.Popen(
            combined,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    @Driver.check_active
    @step(title='call', args=['args'])
    def _call(self, *args):
        combined = self.sigrok.command_prefix + [self.tool]
        if self.sigrok.channels:
            combined += ["-C", self.sigrok.channels]
        combined += list(args)
        self.log.debug("Combined command: %s", combined)
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
        self._filename = filename
        self._basename = os.path.basename(self._filename)
        self.log.debug(
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
            sleep(0.1)

        self._running = True

    @Driver.check_active
    def stop(self):
        assert self._running
        self._running = False
        fnames = ['time']
        fnames.extend(self.sigrok.channels.split(','))
        csv_filename = f'{os.path.splitext(self._basename)[0]}.csv'

        self._process.send_signal(signal.SIGINT)
        stdout, stderr = self._process.communicate()
        self._process.wait()
        self.log.debug("stdout:\n %s\n ----- \n stderr:\n %s", stdout, stderr)

        # Convert from .sr to .csv
        cmd = [
            '-i',
            os.path.join(self._tmpdir, self._basename), '-O', 'csv', '-o',
            os.path.join(self._tmpdir, csv_filename)
        ]
        self._call(*cmd)
        self._process.wait()
        stdout, stderr = self._process.communicate()
        self.log.debug("stdout:\n %s\n ----- \n stderr:\n %s", stdout, stderr)
        if isinstance(self.sigrok, NetworkSigrokUSBDevice):
            subprocess.call([
                'scp', f'{self.sigrok.host}:{os.path.join(self._tmpdir, self._basename)}',
                os.path.join(self._local_tmpdir, self._filename)
            ],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            # get csv from remote host
            subprocess.call([
                'scp', f'{self.sigrok.host}:{os.path.join(self._tmpdir, csv_filename)}',
                os.path.join(self._local_tmpdir, csv_filename)
            ],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            with open(os.path.join(self._local_tmpdir,
                                   csv_filename)) as csv_file:
                # skip first 5 lines of the csv output, contains metadata and fieldnames
                for _ in range(0, 5):
                    next(csv_file)
                return list(csv.DictReader(csv_file, fieldnames=fnames))
        else:
            shutil.copyfile(
                os.path.join(self._tmpdir, self._basename), self._filename
            )
            with open(os.path.join(self._tmpdir, csv_filename)) as csv_file:
                # skip first 5 lines of the csv output, contains metadata and fieldnames
                for _ in range(0, 5):
                    next(csv_file)
                return list(csv.DictReader(csv_file, fieldnames=fnames))

    @Driver.check_active
    def analyze(self, args, filename=None):
        annotation_regex = re.compile(r'(?P<startnum>\d+)-(?P<endnum>\d+) (?P<decoder>[\w\-]+): (?P<annotation>[\w\-]+): (?P<data>".*)')  # pylint: disable=line-too-long
        if not filename and self._filename:
            filename = self._filename
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
