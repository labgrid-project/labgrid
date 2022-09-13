from collections import OrderedDict
from copy import deepcopy

import attr
import pytest

from labgrid import Target, target_factory
from labgrid.driver import Driver
from labgrid.resource import Resource
from labgrid.exceptions import InvalidConfigError, RegistrationError
from labgrid.resource import SerialPort
from labgrid.util.yaml import load

def test_empty():
    t = target_factory.make_target('dummy', {})
    assert isinstance(t, Target)


def test_resources():
    original_config = {
        'resources': OrderedDict([
            ('RawSerialPort', {
                'port': 'foo',
                'speed': 115200,
                'name': 'console',
            }),
        ]),
    }
    config = deepcopy(original_config)
    t = target_factory.make_target('dummy', config)
    assert isinstance(t, Target)
    assert t.get_resource(SerialPort) is not None
    assert config == original_config


def test_drivers():
    original_config = {
        'resources': OrderedDict([
            ('RawSerialPort', {
                'port': 'foo',
                'speed': 115200
            }),
        ]),
        'drivers': OrderedDict([
            ('FakeConsoleDriver', {
                'name': 'console',
            }),
            ('ShellDriver', {
                'name': 'shell',
                'prompt': '',
                'login_prompt': '',
                'username': ''
            }),
        ]),
    }
    config = deepcopy(original_config)
    t = target_factory.make_target('dummy', config)
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
            'cls': 'FooPort',
            'name': None,
        },
        {
            'cls': 'BarPort',
            'name': 'bar'
        },
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
            'cls': 'FooPort',
            'name': None,
        },
        {
            'cls': 'BarPort',
            'name': 'bar'
        },
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
            'cls': 'FooPort',
            'name': None,
        },
        {
            'cls': 'BarPort',
            'name': 'bar'
        },
    ]
    assert data == original_data


def test_normalize_config():
    original_config = {
        'resources': OrderedDict([
            ('RawSerialPort', {
                'port': 'foo',
                'speed': 115200
            }),
        ]),
        'drivers': OrderedDict([
            ('FakeConsoleDriver', {
                'name': 'console',
            }),
        ]),
    }
    config = deepcopy(original_config)
    resources, drivers = target_factory.normalize_config(config)

    assert 'RawSerialPort' in resources
    assert resources['RawSerialPort'] == {None: ({'port': 'foo', 'speed': 115200},)}

    assert 'FakeConsoleDriver' in drivers
    assert drivers['FakeConsoleDriver'] == {'console': ({}, {})}

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
        target_factory.make_resource(
            None, 'NetworkSerialPort', 'serial', {'port': None})
    assert "failed to create" in excinfo.value.msg


def test_driver_param_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_driver(
            None, 'QEMUDriver', 'qemu', {'cpu': 'arm'})
    assert "failed to create" in excinfo.value.msg


def test_resource_class_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_resource(
            None, 'UnknownResource', None, {})
    assert "unknown resource class" in excinfo.value.msg


def test_driver_class_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        target_factory.make_driver(
            None, 'UnknownDriver', None, {})
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
