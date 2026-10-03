import abc


class PortForwardProtocol(abc.ABC):
    """Interface for forwarding TCP ports between the local machine and target.

    Methods return context managers which keep the forwarding active for the
    duration of the context and yield the allocated listening port. A listening
    port of zero requests automatic allocation.
    """

    @abc.abstractmethod
    def local_forward(self, remote_port: int, *, local_port: int = 0):
        """Forward a local port to a remote port on the target."""
        raise NotImplementedError

    @abc.abstractmethod
    def remote_forward(self, local_port: int, *, remote_port: int = 0):
        """Forward a remote port on the target to a local port."""
        raise NotImplementedError
