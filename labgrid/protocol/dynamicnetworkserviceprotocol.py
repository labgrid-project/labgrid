import abc


class DynamicNetworkServiceProtocol(abc.ABC):
    """Abstract class providing the DynamicNetworkServiceProtocol interface"""

    @abc.abstractmethod
    def get_network_service(self):
        """Implementations should return the dynamically created NetworkService"""
        raise NotImplementedError
