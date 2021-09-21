import subprocess
import attr

from ..binding import BindingError, BindingMixin
from .exception import ExecutionError


@attr.s(eq=False)
class Driver(BindingMixin):
    """
    Represents a driver which is used externally or by other drivers. It
    implements functionality based on directly accessing the Resource or by
    building on top of other Drivers.

    Life cycle:
    - create
    - bind (n times)
    - activate
    - usage
    - deactivate
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target is None:
            raise BindingError("Drivers can only be created on a valid target")

    def get_priority(self, protocol):
        """Retrieve the priority for a given protocol

        Arguments:
        protocol - protocol to search for in the MRO

        Returns:
            Int: value of the priority if it is found, 0 otherwise.
        """
        for cls in self.__class__.__mro__:
            prios = getattr(cls, 'priorities', {})
            # we found a matching parent priorities attribute with the matching protocol
            if prios and protocol in prios:
                return prios.get(protocol)
            # If we find the parent protocol, set the priority to 0
            if cls.__name__ == protocol.__name__:
                return 0

        return 0


def check_file(filename, *, command_prefix=[]):
    if subprocess.call(command_prefix + ['test', '-r', filename]) != 0:
        raise ExecutionError(f"File {filename} is not readable")
