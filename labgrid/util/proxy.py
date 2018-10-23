from .ssh import sshmanager

from ..resource.common import NetworkResource, Resource

__all__ = ['proxymanager']

class ProxyManager:
    """The ProxyManager class is only used inside labgrid.util.proxy (similar
    to a singleton), don't instanciate this class, use the exported
    proxymanager instead."""
    @staticmethod
    def get_host_and_port(res, force_proxy=False):
        """ get host and port for a proxy connection from a Resource

        Args:
            res (Resource): The resource to retrieve the proxy for
            force_proxy (:obj:`bool`, optional): whether to always proxy the
                connection, defaults to False

        Returns:
            (host, port) host and port for the proxy connection

        Raises:
            ExecutionError: if the SSH connection/forwarding fails
        """
        assert isinstance(res, Resource)

        if not hasattr(res, 'extra'):
            return res.host, res.port

        if not res.extra.get('proxy') or not res.extra.get("proxy_required"):
            return res.host, res.port

        # res must be a NetworkResource now
        assert isinstance(res, NetworkResource)

        proxy_required = res.extra['proxy_required']
        proxy = res.extra['proxy']
        if proxy_required or force_proxy:
            port = sshmanager.request_forward(proxy, res.host, res.port)
            host = 'localhost'
            return host, port
        return res.host, res.port

proxymanager = ProxyManager()
