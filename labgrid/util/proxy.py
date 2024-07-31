import os

from urllib.parse import urlsplit, urlunsplit, urlparse

from .ssh import sshmanager

from ..resource.common import Resource

__all__ = ['proxymanager']


class ProxyError(Exception):
    pass


class ProxyManager:
    """The ProxyManager class is only used inside labgrid.util.proxy (similar
    to a singleton), don't instanciate this class, use the exported
    proxymanager instead."""
    _force_proxy = os.environ.get("LG_PROXY", None)

    @classmethod
    def force_proxy(cls, force_proxy):
        assert isinstance(force_proxy, str)
        cls._force_proxy = force_proxy

    @classmethod
    def get_host_and_port(cls, res, *, default_port=None, force_port=None):
        """ get host and port for a proxy connection from a Resource

        Args:
            res (Resource): The resource to retrieve the proxy for
            default_port (optional): TCP port to use if no other port is
                configured
            force_port (optional): TCP port to use instead of the one
                configured for the resource

        Returns:
            (host, port) host and port for the proxy connection

        Raises:
            ExecutionError: if the SSH connection/forwarding fails
        """
        assert isinstance(res, Resource)

        prefix = '' if '//' in res.host else '//'
        s = urlparse(prefix + res.host)
        host = s.hostname
        if force_port:
            port = force_port
        elif s.port:
            port = s.port
        else:
            port = getattr(res, 'port', None) or default_port

        extra = getattr(res, 'extra', {})
        if extra:
            proxy_required = extra.get('proxy_required')
            proxy = extra.get('proxy')
            if proxy_required:
                port = sshmanager.request_forward(proxy, host, port)
                host = 'localhost'
                return host, port

        if cls._force_proxy:
            port = sshmanager.request_forward(cls._force_proxy, host, port)
            host = 'localhost'

        return host, port

    @classmethod
    def get_url(cls, url, *, default_port=None):
        assert isinstance(url, str)

        s = urlsplit(url)

        hostname = s.hostname
        port = s.port or default_port

        if hostname is None:
            raise ProxyError(f"Invalid url: {url} does not contain a host")

        if port is None:
            raise ProxyError(f"Invalid url: {url} does not contain a port and no default set")

        if cls._force_proxy:
            port = sshmanager.request_forward(cls._force_proxy, hostname, port)
            hostname = 'localhost'

        if ':' in hostname:
            # IPv6 address
            s = s._replace(netloc=f"[{hostname}]:{port}")
        else:
            s = s._replace(netloc=f"{hostname}:{port}")

        return urlunsplit(s)


    @classmethod
    def get_grpc_url(cls, url, *, default_port=None):
        url = f"//{url}"
        url = proxymanager.get_url(url, default_port=default_port)
        url = url.lstrip("/")
        return url


    @classmethod
    def get_command(cls, res, host, port, ifname=None):
        """get argument list to start a proxy process connected to the target"""
        assert isinstance(res, Resource)

        proxy = cls._force_proxy

        extra = getattr(res, 'extra', {})
        if extra.get('proxy_required') or proxy:  # use specific proxy when needed
            proxy = extra.get('proxy') or proxy

        if not proxy:
            return None

        conn = sshmanager.get(proxy)
        command = conn.get_prefix()
        if ifname:
            command += [
                "--",
                "sudo", "--non-interactive",
                "labgrid-bound-connect", ifname, host, str(port),
            ]
        else:
            if ':' in host:  # IPv6
                host = f"[{host}]"
            command += [
                "-W", f"{host}:{port}"
            ]
        return command


proxymanager = ProxyManager()
