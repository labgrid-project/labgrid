import attr
import subprocess

from ..binding import BindingError, BindingMixin
from .exception import ExecutionError


@attr.s
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


def check_file(filename, *, command_prefix=[]):
    if subprocess.call(command_prefix + ['test', '-r', filename]) != 0:
        raise ExecutionError("File {} is not readable".format(filename))
