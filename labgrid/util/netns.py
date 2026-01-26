import base64
import contextlib
import errno
import functools
import logging
import os
import pickle
import socket
import subprocess
import sys
import tempfile


class NSSocket(socket.socket):
    # __init__ must socket.socket() constructor, due to the way python uses it
    # internally. _attach_remote_sock() can be used after the socket is created
    # to attach the remote socket ID
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__sockid = None
        self.__netns = None

    def _attach_remote_sock(self, sockid, netns):
        self.__sockid = sockid
        self.__netns = netns

        if sockid:
            self.__forward_function("connect")
            self.__forward_function("connect_ex")
            self.__forward_function("bind")

        return self

    def __close_remote_sock(self):
        if self.__sockid:
            self.__netns.socket_close(self.__sockid)
            self.__sockid = None

    def __forward_function(self, name):
        def wrap(*args, **kwargs):
            return self.__netns_call(name, args, kwargs)

        setattr(self, name, wrap)

    def __netns_call(self, func, args, kwargs):
        if not self.__sockid:
            raise OSError(errno.EBADF, os.strerror(errno.EBADF))
        arg_str = base64.b85encode(pickle.dumps((args, kwargs))).decode("ascii")

        err, ret = self.__netns.socket_call(self.__sockid, func, arg_str)
        if err != 0:
            raise OSError(*err)
        return pickle.loads(base64.b85decode(ret))

    def close(self):
        self.__close_remote_sock()
        return super().close()

    def detach(self):
        # NOTE: The detached file descriptor no longer forwards API to the
        # namespace
        self.__close_remote_sock()
        return super().detach()

    def dup(self):
        if self.__sockid:
            ret, fd = self.__netns.socket_dup(self.__sockid)
            if "error" in ret:
                raise OSError(*ret["error"])

            s = self.__class__(fileno=fd)._attach_remote_sock(ret["id"], self.__netns)
            s.settimeout(self.gettimeout())
            return s
        else:
            return super().dup()


class NetNamespace(object):
    @classmethod
    def create(cls, agentwrapper, mac_address=None):
        netns = agentwrapper.load("netns")
        netns.unshare()
        netns.create_tun(address=mac_address)
        return cls(netns)

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

    def get_links(self):
        return self._agent.get_links()

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
        ret, fd = self._agent.create_socket(*args, **kwargs)
        if "error" in ret:
            raise OSError(*ret["error"])
        return NSSocket(fileno=fd)._attach_remote_sock(ret["id"], self._agent)

    def getaddrinfo(self, *args, **kwargs):
        err, result = self._agent.getaddrinfo(*args, **kwargs)
        if err:
            raise OSError(*err)
        return result
