from typing import Optional

from labgrid.remote.common import get_metadata_single_value_by_key

USERNAME_KEY = "x-lg-username"
HOSTNAME_KEY = "x-lg-hostname"
USER_AGENT_KEY = "x-lg-user-agent"


class NoIdentityPresent(Exception):
    """Raised when metadata-based identity information is missing from the request."""


class ClientIdentity:
    """Represents the identity of a connected client, derived from gRPC metadata."""

    def __init__(self, identity_id: str, user_agent: Optional[str]):
        self.id = identity_id
        self.user_agent = user_agent

    def __str__(self):
        return f"ClientIdentity(id={self.id}, user_agent={self.user_agent})"

    @classmethod
    def from_metadata(cls, metadata: tuple):
        """Construct a ClientIdentity from gRPC request metadata.

        Args:
            metadata: A sequence of (key, value) pairs from the gRPC context.

        Returns:
            A ClientIdentity with id set to ``hostname/username`` (or just
            ``hostname`` if no username is present) and (optional) user_agent.

        Raises:
            NoIdentityPresent: If the hostname key is missing from metadata.
        """
        username = get_metadata_single_value_by_key(metadata, USERNAME_KEY)
        hostname = get_metadata_single_value_by_key(metadata, HOSTNAME_KEY)
        user_agent = get_metadata_single_value_by_key(metadata, USER_AGENT_KEY)

        if not hostname:
            raise NoIdentityPresent()

        if username:
            return cls(f"{hostname}/{username}", user_agent)

        return cls(hostname, user_agent)
