from labgrid.driver import NetworkInterfaceDriver
from labgrid.resource import NetworkInterface


def test_forward_remote_auto_allocation(target, mocker):
    NetworkInterface(target, None)
    mocker.patch('labgrid.driver.networkinterfacedriver.AgentWrapper')
    NetworkInterfaceDriver(target, 'netif')
    s = target.get_driver(NetworkInterfaceDriver)
    s.ssh = mocker.Mock()
    s.ssh.add_remote_port_forward.return_value = 42000

    with s.forward_remote(0, 1234) as result:
        assert result is None

    s.ssh.add_remote_port_forward.assert_called_once_with(0, 1234, None)
    s.ssh.remove_remote_port_forward.assert_called_once_with(42000, 1234, None)
    target.deactivate(s)
