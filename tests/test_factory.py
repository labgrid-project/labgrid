from collections import OrderedDict

from labgrid import Target, target_factory
from labgrid.resource import SerialPort


class TestTargetFactory:
    def test_empty(self):
        t = target_factory('dummy', {})
        assert isinstance(t, Target)

    def test_resources(self):
        t = target_factory(
            'dummy', {
                'resources': OrderedDict([
                    ('SerialPort', {
                        'port': 'foo',
                        'speed': 115200
                    }),
                ]),
            }
        )
        assert isinstance(t, Target)
        assert t.get_resource(SerialPort) is not None

    def test_drivers(self, mocker):
        t = target_factory(
            'dummy', {
                'resources': OrderedDict([
                    ('SerialPort', {
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
