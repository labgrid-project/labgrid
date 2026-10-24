import atexit
import subprocess

import pytest

from labgrid.util.ssh import SSHConnection


@pytest.mark.parametrize('requested,allocated,output', [
    (0, 43210, b'43210\n'),
    (43211, 43211, b''),
])
def test_reverse_forward_uses_allocated_port(mocker, requested, allocated, output):
    connection = SSHConnection('exporter')
    mocker.patch.object(connection, 'isconnected', return_value=True)
    control = mocker.patch.object(connection, '_run_socket_command', return_value=output)

    port = connection.add_remote_port_forward(requested, 12345, remote_bind='127.0.0.1')
    assert port == allocated
    control.assert_called_once_with(
        'forward', [f'-R127.0.0.1:{requested}:localhost:12345']
    )
    connection.remove_remote_port_forward(port, 12345, remote_bind='127.0.0.1')
    control.assert_called_with(
        'cancel', [f'-R127.0.0.1:{allocated}:localhost:12345']
    )
    assert not connection._r_forwards


@pytest.mark.parametrize('via_cleanup', [False, True])
def test_failed_cancellation_can_be_retried(mocker, via_cleanup):
    connection = SSHConnection('exporter')
    mocker.patch.object(connection, 'isconnected', return_value=True)
    control = mocker.patch.object(connection, '_run_socket_command', return_value=b'43210\n')
    port = connection.add_remote_port_forward(0, 12345, remote_bind='127.0.0.1')
    control.side_effect = [subprocess.CalledProcessError(255, 'ssh'), b'']

    with pytest.raises(subprocess.CalledProcessError):
        connection.remove_remote_port_forward(port, 12345, remote_bind='127.0.0.1')

    assert connection._r_forwards == {'-R127.0.0.1:43210:localhost:12345'}
    if via_cleanup:
        mocker.patch.object(connection, 'disconnect')
        connection.cleanup()
        atexit.unregister(connection.cleanup)
    else:
        connection.remove_remote_port_forward(port, 12345, remote_bind='127.0.0.1')
    assert not connection._r_forwards
    assert control.call_args_list[-1] == control.call_args_list[-2]


def test_unknown_forward_is_not_cancelled(mocker):
    connection = SSHConnection('exporter')
    mocker.patch.object(connection, 'isconnected', return_value=True)
    control = mocker.patch.object(connection, '_run_socket_command')

    with pytest.raises(KeyError):
        connection.remove_remote_port_forward(43210, 12345, remote_bind='127.0.0.1')

    control.assert_not_called()


def test_failed_reverse_forward_is_not_registered(mocker):
    connection = SSHConnection('exporter')
    mocker.patch.object(connection, 'isconnected', return_value=True)
    mocker.patch.object(
        connection, '_run_socket_command',
        side_effect=subprocess.CalledProcessError(255, 'ssh'),
    )
    with pytest.raises(subprocess.CalledProcessError):
        connection.add_remote_port_forward(0, 12345, remote_bind='127.0.0.1')
    assert not connection._r_forwards
