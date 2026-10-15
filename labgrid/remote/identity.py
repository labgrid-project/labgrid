import logging
from typing import Optional

from labgrid.remote.common import get_metadata_single_value_by_key

NAME_KEY = "x-lg-name"
HOSTNAME_KEY = "x-lg-hostname"
USER_AGENT_KEY = "x-lg-user-agent"


class ClientIdentity:
    """Represents the identity of a connected client, derived from gRPC metadata."""

    def __init__(self, name: str, hostname: str, user_agent: Optional[str]):
        self.name = name
        self.hostname = hostname
        self.user_agent = user_agent

    def __str__(self):
        return f"ClientIdentity(id={self.id}, user_agent={self.user_agent})"

    @property
    def id(self):
        return f"{self.hostname}/{self.name}" if self.name else self.hostname

    @classmethod
    def from_metadata(cls, metadata: tuple):
        """Construct a ClientIdentity from gRPC request metadata.

        Args:
            metadata: A sequence of (key, value) pairs from the gRPC context.

        Returns:
            A ClientIdentity with id set to ``hostname/username`` (or just
            ``hostname`` if no username is present) and (optional) user_agent
            or None if no metadata is supplied.
        """
        name = get_metadata_single_value_by_key(metadata, NAME_KEY)
        hostname = get_metadata_single_value_by_key(metadata, HOSTNAME_KEY)
        user_agent = get_metadata_single_value_by_key(metadata, USER_AGENT_KEY)

        if not hostname:
            return None

        return cls(name, hostname, user_agent)


def infer_peer_identity(clients, context, identity):
    logger = logging.getLogger("infer_peer_identity")

    if identity:
        logger.debug("identity sourced from metadata")
        return identity.id

    logger.debug("identity sourced from self.clients")
    return clients[context.peer()].name
