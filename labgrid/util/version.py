"""
This module contains helper functions for working with version.
"""


def labgrid_version():
    import contextlib
    from importlib.metadata import PackageNotFoundError, version

    lg_version = "unknown"

    with contextlib.suppress(PackageNotFoundError):
        lg_version = version("labgrid")

    return lg_version
