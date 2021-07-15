from collections import OrderedDict

import attr
import pytest
import io

from labgrid import Target, target_factory
from labgrid.driver import Driver
from labgrid.resource import Resource
from labgrid.exceptions import InvalidConfigError, RegistrationError
from labgrid.resource import SerialPort
from labgrid.util.yaml import load

@pytest.fixture(scope='function')
def foo_yaml():
    string = """
    FooPort: {}
    BarPort:
      name: bar
    """
    return io.StringIO(string)


@pytest.fixture(scope='function')
def list_yaml():
    string = """
    - cls: FooPort
    - cls: BarPort
      name: bar
    """
    return io.StringIO(string)


def test_empty():
    t = target_factory.make_target('dummy', {})
    assert isinstance(t, Target)


def test_resources():
    t = target_factory.make_target(
        'dummy', {
            'resources': OrderedDict([
                ('RawSerialPort', {
                    'port': 'foo',
                    'speed': 115200
                }),
            ]),
        }
    )
    assert isinstance(t, Target)
    assert t.get_resource(SerialPort) is not None


def test_drivers():
    t = target_factory.make_target(
        'dummy', {
            'resources': OrderedDict([
                ('RawSerialPort', {
                    'port': 'foo',
                    'speed': 115200
                }),
            ]),
            'drivers': OrderedDict([
                ('FakeConsoleDriver', {}),
                ('ShellDriver', {
                    'prompt': '',
                    'login_prompt': '',
                    'username': ''
                }),
            ]),
        }
    )
    assert isinstance(t, Target)
    assert t.get_resource(SerialPort) is not None


def test_convert_dict(foo_yaml):
    data = load(foo_yaml, '.')
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


def test_convert_simple_list(foo_yaml):
    data = load(foo_yaml, '.')
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


def test_convert_explicit_list(list_yaml):
    data = load(list_yaml, '.')
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


def test_convert_error():
    with pytest.raises(InvalidConfigError) as excinfo:
        data = load(io.StringIO("""
                - {}
                """), '.')
        target_factory._convert_to_named_list(data)
    assert "invalid empty dict as list item" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load(io.StringIO("""
                - "error"
                """), '.')
        target_factory._convert_to_named_list(data)
    assert "invalid list item type <class 'str'> (should be dict)" in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load(io.StringIO("""
                - name: "bar"
                  extra: "baz"
                """), '.')
        target_factory._convert_to_named_list(data)
    assert "missing 'cls' key in " in excinfo.value.msg

    with pytest.raises(InvalidConfigError) as excinfo:
        data = load(io.StringIO("""
                - one:
                - two: {}
                """), '.')
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
