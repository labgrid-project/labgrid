from collections import OrderedDict
from copy import deepcopy

import attr
import pytest

from labgrid import Target, target_factory
from labgrid.driver import Driver
from labgrid.exceptions import InvalidConfigError, RegistrationError
from labgrid.factory import TargetFactory
from labgrid.plugins.manager import plugin_manager
from labgrid.resource import Resource, SerialPort
from labgrid.util.yaml import load


def test_empty():
    t = target_factory.make_target("dummy", {})
    assert isinstance(t, Target)


def test_resources():
    original_config = {
        "resources": OrderedDict(
            [
                (
                    "RawSerialPort",
                    {
                        "port": "foo",
                        "speed": 115200,
                        "name": "console",
                    },
                ),
            ]
        ),
    }
    config = deepcopy(original_config)
    t = target_factory.make_target("dummy", config)
    assert isinstance(t, Target)
    assert t.get_resource(SerialPort) is not None
    assert config == original_config


def test_drivers():
    original_config = {
        "resources": OrderedDict(
            [
                ("RawSerialPort", {"port": "foo", "speed": 115200}),
            ]
        ),
        "drivers": OrderedDict(
            [
                (
                    "FakeConsoleDriver",
                    {
                        "name": "console",
                    },
                ),
                ("ShellDriver", {"name": "shell", "prompt": "", "login_prompt": "", "username": ""}),
            ]
        ),
    }
    config = deepcopy(original_config)
    t = target_factory.make_target("dummy", config)
    assert isinstance(t, Target)
    assert t.get_resource(SerialPort) is not None
    assert config == original_config


def test_convert_dict():
    original_data = load("""
    FooPort: {}
    BarPort:
      name: bar
    """)
    data = deepcopy(original_data)
    l = target_factory._convert_to_named_list(data)
    assert l == [
        {
            "cls": "FooPort",
            "name": None,
        },
        {"cls": "BarPort", "name": "bar"},
    ]
    assert data == original_data


def test_convert_simple_list():
    original_data = load("""
    - FooPort: {}
    - BarPort:
        name: bar
    """)
    data = deepcopy(original_data)
    l = target_factory._convert_to_named_list(data)
    assert l == [
        {
            "cls": "FooPort",
            "name": None,
        },
        {"cls": "BarPort", "name": "bar"},
    ]
    assert data == original_data


def test_convert_explicit_list():
    original_data = load("""
    - cls: FooPort
    - cls: BarPort
      name: bar
    """)
    data = deepcopy(original_data)
    l = target_factory._convert_to_named_list(data)
    assert l == [
        {
            "cls": "FooPort",
            "name": None,
        },
        {"cls": "BarPort", "name": "bar"},
    ]
    assert data == original_data


def test_normalize_config():
    original_config = {
        "resources": OrderedDict(
            [
                ("RawSerialPort", {"port": "foo", "speed": 115200}),
            ]
        ),
        "drivers": OrderedDict(
            [
                (
                    "FakeConsoleDriver",
                    {
                        "name": "console",
                    },
                ),
            ]
        ),
    }
    config = deepcopy(original_config)
    resources, drivers = target_factory.normalize_config(config)

    assert "RawSerialPort" in resources
    assert resources["RawSerialPort"] == {None: ({"port": "foo", "speed": 115200},)}

    assert "FakeConsoleDriver" in drivers
    assert drivers["FakeConsoleDriver"] == {"console": ({}, {})}

    assert config == original_config


def test_convert_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        - {}
        """)
        target_factory._convert_to_named_list(data)
    assert "invalid empty dict as list item" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        - "error"
        """)
        target_factory._convert_to_named_list(data)
    assert "invalid list item type <class 'str'> (should be dict)" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        - name: "bar"
          extra: "baz"
        """)
        target_factory._convert_to_named_list(data)
    assert "missing 'cls' key in OrderedDict(" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load("""
        - one:
        - two: {}
        """)
        target_factory._convert_to_named_list(data)
    assert "invalid list item, add empty dict for no arguments" in excinfo.value.msg


def test_resource_param_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_resource(None, "NetworkSerialPort", "serial", {"port": None})
    assert "failed to create" in excinfo.value.msg


def test_driver_param_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_driver(None, "QEMUDriver", "qemu", {"cpu": "arm"})
    assert "failed to create" in excinfo.value.msg


def test_resource_class_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_resource(None, "UnknownResource", None, {})
    assert "unknown resource class" in excinfo.value.msg


def test_driver_class_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_driver(None, "UnknownDriver", None, {})
    assert "unknown driver class" in excinfo.value.msg


def test_register_same_driver():
    @attr.s
    class SameDriver(Driver):
        pass

    with pytest.raises(RegistrationError) as excinfo:
        target_factory.reg_driver(SameDriver)
        target_factory.reg_driver(SameDriver)
    assert "driver with name" in excinfo.value.msg


def test_register_same_resource():
    @attr.s
    class SameResource(Resource):
        pass

    with pytest.raises(RegistrationError) as excinfo:
        target_factory.reg_driver(SameResource)
        target_factory.reg_driver(SameResource)
    assert "driver with name" in excinfo.value.msg


def test_plugin_resource_registration(mocker):
    class MockResource(Resource):
        pass

    mock_hook = mocker.patch.object(plugin_manager.hook, "labgrid_register_resources")
    mock_hook.return_value = [[MockResource]]

    tmp_target_factory = TargetFactory()
    tmp_target_factory.register_plugins()
    cls_name = MockResource.__name__
    mock_hook.assert_called_once()
    assert cls_name in tmp_target_factory.resources
    assert MockResource == tmp_target_factory.resources.get(cls_name)
    assert cls_name in tmp_target_factory.all_classes
    assert MockResource == tmp_target_factory.all_classes.get(cls_name)


def test_plugin_driver_registration(mocker):
    class MockDriver(Driver):
        pass

    mock_hook = mocker.patch.object(plugin_manager.hook, "labgrid_register_drivers")
    mock_hook.return_value = [[MockDriver]]

    tmp_target_factory = TargetFactory()
    tmp_target_factory.register_plugins()
    cls_name = MockDriver.__name__
    mock_hook.assert_called_once()
    assert cls_name in tmp_target_factory.drivers
    assert MockDriver == tmp_target_factory.drivers.get(cls_name)
    assert cls_name in tmp_target_factory.all_classes
    assert MockDriver == tmp_target_factory.all_classes.get(cls_name)


@pytest.fixture
def mock_plugin_classes(mocker):
    class MockResource(Resource):
        pass

    class MockDriver(Driver):
        bindings = {"res": MockResource}

    mock_res_hook = mocker.patch.object(plugin_manager.hook, "labgrid_register_resources")
    mock_res_hook.return_value = [[MockResource]]

    mock_drv_hook = mocker.patch.object(plugin_manager.hook, "labgrid_register_drivers")
    mock_drv_hook.return_value = [[MockDriver]]

    return MockResource, MockDriver


def test_plugin_make_target(mock_plugin_classes):
    mock_resource_cls, mock_driver_cls = mock_plugin_classes

    config = {
        "resources": [{"cls": "MockResource", "name": "mock_res"}],
        "drivers": [{"cls": "MockDriver", "name": "mock_drv"}],
    }

    tmp_target_factory = TargetFactory()
    tmp_target_factory.register_plugins()
    t = tmp_target_factory.make_target("test", config)

    assert t.get_resource(mock_resource_cls, name="mock_res") is not None
    assert t.get_driver(mock_driver_cls, name="mock_drv") is not None


def test_plugin_integration_with_builtins(mock_plugin_classes):
    mock_resource_cls, mock_driver_cls = mock_plugin_classes

    # The global target_factory already has built-in resources/drivers
    initial_resources = set(target_factory.resources.keys())
    initial_drivers = set(target_factory.drivers.keys())

    # Simulate loading plugins by calling register_plugins
    target_factory.register_plugins()

    # Check that plugin classes are added alongside built-ins
    assert mock_resource_cls.__name__ in target_factory.resources
    assert mock_driver_cls.__name__ in target_factory.drivers

    # Ensure built-ins are still present
    assert initial_resources.issubset(target_factory.resources.keys())
    assert initial_drivers.issubset(target_factory.drivers.keys())
