# pylint: disable=no-member
import logging
import os.path
import re
import subprocess
import shutil
import signal
import tempfile
import uuid
import csv

from time import sleep

import attr

from ..factory import target_factory
from ..resource.remote import NetworkSigrokUSBDevice
from ..resource.udev import SigrokUSBDevice
from ..resource.sigrok import SigrokDevice
from ..step import step
from .common import Driver, check_file


@target_factory.reg_driver
@attr.s(eq=False)
class SigrokDriver(Driver):
    """The SigrokDriver uses sigrok-cli to record samples and expose them as python dictionaries.

    Args:
        bindings (dict): driver to use with sigrok
    """
    bindings = {
        "sigrok": {SigrokUSBDevice, NetworkSigrokUSBDevice, SigrokDevice},
    }

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

    def _get_sigrok_prefix(self):
        if isinstance(self.sigrok, (NetworkSigrokUSBDevice, SigrokUSBDevice)):
            prefix = [
                self.tool, "-d", "{}:conn={}.{}".format(
                    self.sigrok.driver, self.sigrok.busnum, self.sigrok.devnum
                ), "-C", self.sigrok.channels
            ]
        else:
            prefix = [
                self.tool, "-d", self.sigrok.driver, "-C", self.sigrok.channels
            ]
        return self.sigrok.command_prefix + prefix

    def _create_tmpdir(self):
        if isinstance(self.sigrok, NetworkSigrokUSBDevice):
            self._tmpdir = '/tmp/labgrid-sigrok-{}'.format(uuid.uuid1())
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
        combined = self.sigrok.command_prefix + [
            self.tool, "-C", self.sigrok.channels
        ] + list(args)
        self.log.debug("Combined command: %s", combined)
        self._process = subprocess.Popen(
            combined,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    @Driver.check_active
    def capture(self, filename, samplerate="200k"):
        self._filename = filename
        self._basename = os.path.basename(self._filename)
        self.log.debug(
            "Saving to: %s with basename: %s", self._filename, self._basename
        )
        cmd = [
            "-l", "4", "--config", "samplerate={}".format(samplerate),
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
        csv_filename = '{}.csv'.format(os.path.splitext(self._basename)[0])

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
                'scp', '{}:{}'.format(
                    self.sigrok.host,
                    os.path.join(self._tmpdir, self._basename)
                ),
                os.path.join(self._local_tmpdir, self._filename)
            ],
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            # get csv from remote host
            subprocess.call([
                'scp', '{}:{}'.format(
                    self.sigrok.host, os.path.join(self._tmpdir, csv_filename)
                ),
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
                return [x for x in csv.DictReader(csv_file, fieldnames=fnames)]
        else:
            shutil.copyfile(
                os.path.join(self._tmpdir, self._basename), self._filename
            )
            with open(os.path.join(self._tmpdir, csv_filename)) as csv_file:
                # skip first 5 lines of the csv output, contains metadata and fieldnames
                for _ in range(0, 5):
                    next(csv_file)
                return [x for x in csv.DictReader(csv_file, fieldnames=fnames)]

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
