import contextlib
import functools
import logging
import os
import socket
import subprocess
import tempfile
import sys


class NetNamespace(object):
    def __init__(self, agent):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._agent = agent

    @functools.cached_property
    def prefix(self):
        return self._agent.get_prefix()

    @functools.cached_property
    def intf(self):
        return self._agent.get_intf()

    @functools.cached_property
    def ifindex(self):
        links = self._agent.get_links()
        for intf in links:
            if intf["ifname"] == self.intf:
                return intf["ifindex"]
        raise KeyError(f"Interface {self.intf} not found")

    def _get_cmd(self, command):
        if isinstance(command, str):
            return self.prefix + ["--wd=" + os.getcwd(), "--", "/bin/sh", "-c", command]
        return self.prefix + ["--wd=" + os.getcwd(), "--"] + command

    def run(self, command, **kwargs):
        cmd = self._get_cmd(command)
        self.logger.debug("Running %s", cmd)
        return subprocess.run(cmd, **kwargs)

    def Popen(self, command, **kwargs):
        cmd = self._get_cmd(command)
        self.logger.debug("Popen %s", cmd)
        return subprocess.Popen(cmd, **kwargs)

    @contextlib.contextmanager
    def _create_script(self, script):
        with tempfile.NamedTemporaryFile("w") as s:
            s.write(script)
            s.flush()

            yield [sys.executable, s.name]

    def run_script(self, script, script_args=[], **kwargs):
        with self._create_script(script) as command:
            return self.run(command + script_args, **kwargs)

    @contextlib.contextmanager
    def Popen_script(self, script, script_args=[], **kwargs):
        with self._create_script(script) as command:
            with self.Popen(command + script_args, **kwargs) as p:
                yield p

    def socket(self, *args, **kwargs):
        err, fd = self._agent.create_socket(*args, **kwargs)
        if err:
            raise OSError(*err)
        return socket.socket(fileno=fd)

    def connect(self, *args, **kwargs):
        err, fd = self._agent.connect(*args, **kwargs)
        if err:
            raise OSError(*err)
        return socket.socket(fileno=fd)

    def bind(self, *args, **kwargs):
        err, fd = self._agent.bind(*args, **kwargs)
        if err:
            raise OSError(*err)
        return socket.socket(fileno=fd)

    def getaddrinfo(self, *args, **kwargs):
        err, result = self._agent.getaddrinfo(*args, **kwargs)
        if err:
            raise OSError(*err)
        return result
