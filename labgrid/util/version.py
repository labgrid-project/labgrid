"""
This module contains helper functions for working with version.
"""


def labgrid_version():
    try:
        from .._version import __version__
        return __version__
    except ModuleNotFoundError:
        pass

    import contextlib
    from importlib.metadata import PackageNotFoundError, version

    lg_version = "unknown"

    with contextlib.suppress(PackageNotFoundError):
        lg_version = version("labgrid")

    return lg_version
