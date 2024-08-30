import pytest

from labgrid.driver import ShellDriver, ExecutionError
from labgrid.exceptions import NoDriverFoundError

from ipaddress import IPv4Interface


class TestShellDriver:
    def test_instance(self, target, serial_driver):
        s = ShellDriver(target, "shell", "", "", "")
        assert (isinstance(s, ShellDriver))

    def test_no_driver(self, target):
        with pytest.raises(NoDriverFoundError):
            ShellDriver(target, "shell", "", "", "")

    def test_run(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = ShellDriver(t, "shell", prompt='dummy', login_prompt='dummy', username='dummy')
        d.on_activate = mocker.MagicMock()
        d = t.get_driver('ShellDriver')
        d._run = mocker.MagicMock(return_value=(['success'], [], 0))
        res = d.run_check("test")
        assert res == ['success']
        res = d.run("test")
        assert res == (['success'], [], 0)

    def test_run_error(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = ShellDriver(t, "shell", prompt='dummy', login_prompt='dummy', username='dummy')
        d.on_activate = mocker.MagicMock()
        d = t.get_driver('ShellDriver')
        d._run = mocker.MagicMock(return_value=(['error'], [], 1))
        with pytest.raises(ExecutionError):
            res = d.run_check("test")
        res = d.run("test")
        assert res == (['error'], [], 1)

    def test_run_with_timeout(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = ShellDriver(t, "shell", prompt='dummy', login_prompt='dummy', username='dummy')
        d.on_activate = mocker.MagicMock()
        d = t.get_driver('ShellDriver')
        d._run = mocker.MagicMock(return_value=(['success'], [], 0))
        res = d.run_check("test", timeout=30.0)
        assert res == ['success']
        res = d.run("test")
        assert res == (['success'], [], 0)

    def test_default_interface_device_name(self, target_with_fakeconsole, mocker):
        fake_default_route_show = "default via 10.0.2.2 dev br-lan  src 10.0.2.15"

        t = target_with_fakeconsole
        d = ShellDriver(t, "shell", prompt="dummy", login_prompt="dummy", username="dummy")
        d.on_activate = mocker.MagicMock()
        d = t.get_driver("ShellDriver")
        d._run = mocker.MagicMock(return_value=([fake_default_route_show], [], 0))

        res = d.get_default_interface_device_name()
        assert res == "br-lan"

    def test_get_ip_addresses(self, target_with_fakeconsole, mocker):
        fake_ip_addr_show = r"""
18: br-lan.42    inet 192.168.42.1/24 brd 192.168.42.255 scope global br-lan.42\       valid_lft forever preferred_lft forever
18: br-lan.42    inet6 fe80::9683:c4ff:fea6:fb6b/64 scope link \       valid_lft forever preferred_lft forever
"""

        t = target_with_fakeconsole
        d = ShellDriver(t, "shell", prompt='dummy', login_prompt='dummy', username='dummy')
        d.on_activate = mocker.MagicMock()
        d = t.get_driver('ShellDriver')
        d._run = mocker.MagicMock(return_value=([fake_ip_addr_show], [], 0))

        res = d.get_ip_addresses("br-lan.42")
        assert res[0] == IPv4Interface("192.168.42.1/24")

    def test_get_ip_addresses_default(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = ShellDriver(t, "shell", prompt="dummy", login_prompt="dummy", username="dummy")
        d.on_activate = mocker.MagicMock()
        d = t.get_driver("ShellDriver")
        d._run = mocker.MagicMock()
        d._run.side_effect = [
            (["default via 192.168.42.255 dev br-lan.42  src 192.168.42.1"], [], 0),
            (
                [
                    r"""
18: br-lan.42    inet 192.168.42.1/24 brd 192.168.42.255 scope global br-lan.42\       valid_lft forever preferred_lft forever
18: br-lan.42    inet6 fe80::9683:c4ff:fea6:fb6b/64 scope link \       valid_lft forever preferred_lft forever
"""
                ],
                [],
                0,
            ),
        ]

        res = d.get_ip_addresses()
        assert res[0] == IPv4Interface("192.168.42.1/24")
