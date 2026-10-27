"""
Describes the USB hubs in a lab, so that a device's ID_PATH can be built from
a hub name and a port number instead of being written out in full
"""

from ..exceptions import InvalidConfigError
from .yaml import load


class USBHubs:
    """A set of USB hubs, each with a base path and a suffix for each port

    The description is a dict which maps each hub name to a dict holding the
    hub's 'base' path, e.g. 'pci-0000:00:14.0-usb-0:10', and its 'ports',
    which maps each port number on the hub's case to the path suffix of that
    port, e.g. {1: '2.1', 2: '2.2'}

    Args:
        hubs (dict): Hub description, as above
        filename (str): File the description was read from, used in error
            messages
    """

    def __init__(self, hubs, filename="hubs"):
        self.filename = filename
        if not isinstance(hubs, dict):
            raise InvalidConfigError(
                f"{filename}: expected a mapping of hub names"
            )
        self.hubs = {}
        for name, hub in hubs.items():
            if not isinstance(hub, dict):
                raise InvalidConfigError(
                    f"{filename}: hub '{name}' must be a mapping"
                )
            base = hub.get("base")
            if not isinstance(base, str):
                raise InvalidConfigError(
                    f"{filename}: hub '{name}' needs a 'base' string"
                )
            ports = hub.get("ports")
            if not isinstance(ports, dict):
                raise InvalidConfigError(
                    f"{filename}: hub '{name}' needs a 'ports' mapping"
                )
            for port, suffix in ports.items():
                # YAML reads an unquoted 2.1 as a float, which turns 1.10
                # into 1.1, so insist on strings
                if not isinstance(suffix, str):
                    raise InvalidConfigError(
                        f"{filename}: hub '{name}' port {port}: suffix {suffix!r} must be a quoted string"
                    )
            # Port numbers may be given as integers or strings
            self.hubs[str(name)] = (
                base,
                {str(port): suffix for port, suffix in ports.items()},
            )

    @classmethod
    def from_file(cls, filename):
        """Read a hub description from a YAML file

        Args:
            filename (str): Path to the file

        Returns:
            USBHubs: The hubs described in the file
        """
        with open(filename) as f:
            return cls(load(f), filename)

    def path(self, hub, port, iface=None):
        """Get the ID_PATH for a port on a hub

        Args:
            hub (str): Hub name
            port (int or str): Port number on that hub
            iface (str): USB interface to append, e.g. '1.0', or None for
                the path of the device itself

        Returns:
            str: ID_PATH, e.g. 'pci-0000:00:14.0-usb-0:10.2.1:1.0'

        Raises:
            InvalidConfigError: The hub or port is not defined
        """
        try:
            base, ports = self.hubs[str(hub)]
        except KeyError:
            raise InvalidConfigError(
                f"{self.filename}: hub '{hub}' is not defined"
            ) from None
        suffix = ports.get(str(port))
        if suffix is None:
            raise InvalidConfigError(
                f"{self.filename}: port {port} is not defined on hub '{hub}'"
            )
        path = f"{base}.{suffix}"
        if iface is not None:
            path += f":{iface}"
        return path
