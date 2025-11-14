from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

import pluggy

import labgrid.plugins.target_factory_hookspecs as target_factory_module

from .constants import LABGRID_ENTRY_POINT

plugin_manager = pluggy.PluginManager(LABGRID_ENTRY_POINT)
plugin_manager.add_hookspecs(target_factory_module)


class PluginRegistrar(ABC):
    @abstractmethod
    def register_plugins(self):
        raise NotImplementedError


def load_plugins(registrars: Sequence[PluginRegistrar]):
    plugin_manager.load_setuptools_entrypoints(LABGRID_ENTRY_POINT)

    for registrar in registrars:
        registrar.register_plugins()
