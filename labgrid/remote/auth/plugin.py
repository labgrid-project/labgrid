import logging
import warnings
from importlib.metadata import entry_points
from typing import List, Mapping, Protocol, Optional, runtime_checkable

from labgrid.remote.identity import ClientIdentity

NAME_KEY = "x-lg-name"
HOSTNAME_KEY = "x-lg-hostname"
USER_AGENT_KEY = "x-lg-user-agent"


@runtime_checkable
class ClientAuthPlugin(Protocol):
    def metadata(self) -> Mapping[str, List[str]]:
        """Produces the gRPC metadata pairs to add to each RPC call's metadata."""
        ...


def get_client_auth_plugin_names():
    try:
        auth_plugins = entry_points(group="labgrid.auth.plugin.client")
        auth_plugin_names = ["default"] + [i.name for i in auth_plugins]

        if len(auth_plugin_names) != len(set(auth_plugin_names)):
            warnings.warn("Duplicate auth plugin names. Please ensure that plugin names are unique.", UserWarning)
    except Exception:
        return ["default"]

    return auth_plugin_names


def get_client_auth_plugin(
    username: Optional[str], hostname: str, user_agent: str, plugin_name: Optional[str]
) -> ClientAuthPlugin:
    identity = {
        "username": username,
        "hostname": hostname,
        "user_agent": user_agent,
    }
    auth_plugin = DefaultClientAuthPlugin(**identity)

    if plugin_name:
        if plugin_name == "default":
            return auth_plugin

        logging.debug("Desired auth plugin: %s", plugin_name)
        auth_plugins = entry_points(group="labgrid.auth.plugin.client")

        try:
            logging.debug("Possible auth plugins: %s", auth_plugins)
            plugin_cls = auth_plugins[plugin_name].load()
            if not issubclass(plugin_cls, ClientAuthPlugin):
                raise Exception("Plugin does not conform to ClientAuthPlugin Protocol")
            auth_plugin = plugin_cls()
        except Exception as e:
            raise PluginLoadException("Unable to load client plugin") from e

    return auth_plugin


class DefaultClientAuthPlugin(ClientAuthPlugin):
    def __init__(self, username: Optional[str], hostname: str, user_agent: Optional[str]):
        super().__init__()
        self.username = username
        self.hostname = hostname
        self.user_agent = user_agent

    def metadata(self) -> Mapping[str, List[str]]:
        metadata = {
            HOSTNAME_KEY: [self.hostname],
        }
        if self.username:
            metadata[NAME_KEY] = [self.username]
        if self.user_agent:
            metadata[USER_AGENT_KEY] = [self.user_agent]
        return metadata


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


class PluginLoadException(Exception):
    pass


def get_coordinator_auth_plugin_names():
    try:
        auth_plugins = entry_points(group="labgrid.auth.plugin.coordinator")
        auth_plugin_names = ["default"] + [i.name for i in auth_plugins]

        if len(auth_plugin_names) != len(set(auth_plugin_names)):
            warnings.warn("Duplicate auth plugin names. Please ensure that plugin names are unique.", UserWarning)
    except Exception:
        return ["default"]

    return auth_plugin_names


def get_coordinator_auth_plugin(plugin_name: Optional[str]) -> CoordinatorAuthPlugin:
    auth_plugin = DefaultCoordinatorAuthPlugin()

    if plugin_name:
        if plugin_name == "default":
            return auth_plugin

        logging.debug("Desired auth plugin: %s", plugin_name)
        auth_plugins = entry_points(group="labgrid.auth.plugin.coordinator")

        try:
            logging.debug("Possible auth plugins: %s", auth_plugins)
            plugin_cls = auth_plugins[plugin_name].load()
            if not issubclass(plugin_cls, CoordinatorAuthPlugin):
                raise Exception("Plugin does not conform to CoordinatorAuthPlugin Protocol")
            auth_plugin = plugin_cls()
        except Exception as e:
            raise PluginLoadException("Unable to load Coordinator plugin") from e

    return auth_plugin


def clientidentity_from_plugin(plugin: CoordinatorAuthPlugin, metadata: tuple) -> ClientIdentity:
    identity = plugin.authenticate(metadata)
    return identity


class DefaultCoordinatorAuthPlugin(CoordinatorAuthPlugin):
    def get_single_value_metadata(self, metadata: Mapping[str, List[str]], key: str) -> Optional[str]:
        values = metadata.get(key)

        if not values:
            return None

        if len(values) != 1:
            return None

        return values[0]

    def authenticate(self, metadata: Mapping[str, List[str]]) -> ClientIdentity:
        """Construct a ClientIdentity from gRPC request metadata.

        Args:
            metadata: A sequence of (key, value) pairs from the gRPC context.

        Returns:
            A ClientIdentity with id set to ``hostname/username`` (or just
            ``hostname`` if no username is present) and (optional) user_agent
            or None if no metadata is supplied.

        Raises:
            NoIdentityPresent: If the hostname key is missing from metadata.
        """
        username = self.get_single_value_metadata(metadata, NAME_KEY)
        hostname = self.get_single_value_metadata(metadata, HOSTNAME_KEY)
        user_agent = self.get_single_value_metadata(metadata, USER_AGENT_KEY)

        if not hostname:
            return None

        if username:
            return ClientIdentity(f"{hostname}/{username}", user_agent)

        return ClientIdentity(hostname, user_agent)
