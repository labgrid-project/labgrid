import importlib
import importlib.metadata

import pluggy
import pytest

from labgrid.driver import Driver
from labgrid.plugins import target_factory_hookspecs
from labgrid.plugins.constants import LABGRID_ENTRY_POINT
from labgrid.plugins.manager import load_plugins, plugin_manager
from labgrid.resource import Resource


def test_plugin_manager_creation():
    assert isinstance(plugin_manager, pluggy.PluginManager)
    assert plugin_manager.project_name == LABGRID_ENTRY_POINT


def test_hookspecs_added(mocker):
    mock_add_hookspecs = mocker.patch.object(pluggy.PluginManager, "add_hookspecs")

    manager_module = importlib.import_module("labgrid.plugins.manager")
    importlib.reload(manager_module)

    mock_add_hookspecs.assert_called_once_with(target_factory_hookspecs)


def test_entrypoints_loaded(mocker):
    mock_load = mocker.patch.object(pluggy.PluginManager, "load_setuptools_entrypoints")

    load_plugins([])

    mock_load.assert_called_once_with(LABGRID_ENTRY_POINT)


@pytest.fixture
def mock_plugin():
    hookimpl = pluggy.HookimplMarker(LABGRID_ENTRY_POINT)

    class MockPlugin:
        @hookimpl
        def labgrid_register_resources(self):
            class MockResource(Resource):
                pass

            return [MockResource]

        @hookimpl
        def labgrid_register_drivers(self):
            class MockDriver(Driver):
                pass

            return [MockDriver]

    return MockPlugin


@pytest.fixture
def mocked_entrypoints(mocker, mock_plugin):
    mock_entry_point = mocker.Mock()
    mock_entry_point.group = LABGRID_ENTRY_POINT
    mock_entry_point.name = "mock_plugin"
    mock_entry_point.load.return_value = mock_plugin()

    mock_dist = mocker.Mock()
    mock_dist.entry_points = [mock_entry_point]

    mocker.patch("importlib.metadata.distributions").return_value = [mock_dist]


@pytest.fixture
def mocked_plugin_manager(mocked_entrypoints):
    manager_module = importlib.import_module("labgrid.plugins.manager")
    importlib.reload(manager_module)
    manager_module.load_plugins([])

    return manager_module.plugin_manager


def test_hook_calls(mocked_plugin_manager):
    # Now test hook calls
    resources = mocked_plugin_manager.hook.labgrid_register_resources()
    drivers = mocked_plugin_manager.hook.labgrid_register_drivers()

    assert len(resources) == 1
    assert issubclass(resources[0][0], Resource)
    assert len(drivers) == 1
    assert issubclass(drivers[0][0], Driver)
