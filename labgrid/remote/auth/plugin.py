from typing import List, Mapping, Protocol, runtime_checkable
from labgrid.remote.identity import ClientIdentity


@runtime_checkable
class ClientAuthPlugin(Protocol):
    def metadata(self) -> Mapping[str, List[str]]:
        """Produces the gRPC metadata pairs to add to each RPC call's metadata."""
        ...


class IdentityError(Exception):
    """Exception to be raised when the provided metadata cannot be resolved
    to a valid identity."""

    pass


@runtime_checkable
class CoordinatorAuthPlugin(Protocol):
    def authenticate(self, metadata: Mapping[str, List[str]]) -> ClientIdentity:
        """Consumes the gRPC metadata, performs identity provider-specific
        validation and, if successful, emits a populated ClientIdentity."""
        ...


def clientidentity_from_plugin(plugin: CoordinatorAuthPlugin, metadata: tuple) -> ClientIdentity:
    identity = plugin.authenticate(metadata)
    return identity