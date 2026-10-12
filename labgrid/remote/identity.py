import logging
from typing import Optional, Set

from labgrid.remote.auth.capability import Capability

NAME_KEY = "x-lg-name"
HOSTNAME_KEY = "x-lg-hostname"
USER_AGENT_KEY = "x-lg-user-agent"
ALL_CAPABILITIES = set(e for e in Capability)


class ClientIdentity:
    """Represents the identity of a connected client, derived from gRPC metadata."""

    def __init__(
        self,
        identity_id: str,
        user_agent: Optional[str] = None,
        capabilities: Set[Capability] = ALL_CAPABILITIES,
    ) -> None:
        self.id = identity_id
        self.user_agent = user_agent
        self.capabilities = capabilities

    def __str__(self):
        return f"ClientIdentity(id={self.id}, user_agent={self.user_agent})"


def infer_peer_identity(clients, context, identity):
    logger = logging.getLogger("infer_peer_identity")

    if identity:
        logger.debug("identity sourced from metadata")
        return identity.id

    logger.debug("identity sourced from self.clients")
    return clients[context.peer()].name
