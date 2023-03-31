"""
This module contains helper functions for working with version.
"""


import contextlib
from importlib.metadata import PackageNotFoundError, version


def labgrid_version():
    lg_version = "unknown"

    with contextlib.suppress(PackageNotFoundError):
        lg_version = version("labgrid")

    return lg_version
