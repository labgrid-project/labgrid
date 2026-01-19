from __future__ import annotations

from collections.abc import Sequence

import pluggy

from .constants import LABGRID_ENTRY_POINT

hookspec = pluggy.HookspecMarker(LABGRID_ENTRY_POINT)


@hookspec
def labgrid_register_drivers() -> Sequence[type]:
    """
    Hook specification for registering driver classes.

    Plugins implementing this hook should return a list of driver classes
    (subclasses of labgrid.driver.Driver) to be dynamically registered
    with labgrid's TargetFactory.

    Returns:
        Sequence[type]: List of driver classes to register.
    """
    pass


@hookspec
def labgrid_register_resources() -> Sequence[type]:
    """
    Hook specification for registering resource classes.

    Plugins implementing this hook should return a list of resource classes
    (subclasses of labgrid.resource.Resource) to be dynamically registered
    with labgrid's TargetFactory.

    Returns:
        Sequence[type]: List of resource classes to register.
    """
    pass
