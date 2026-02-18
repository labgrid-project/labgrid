import pytest
import socket

from labgrid.driver import Eth008DigitalOutputDriver
from labgrid.resource import Eth008DigitalOutput


@pytest.fixture(scope="function")
def mock_tcp_server(mocker):
    """Mock the ETH008 TCP server responses."""
    state = 0x00  # Initial state: all relays OFF

    # Track sent commands for verification
    sent_commands = []

    def mock_sendall(data):
        """Mock socket.sendall."""
        nonlocal state, sent_commands

        sent_commands.append(data)

        if len(data) == 1 and data[0] == 0x24:
            return
        elif len(data) == 3:
            command = data[0]
            relay_index = data[1]

            if command == 0x20:  # Digital Active (ON)
                state |= (1 << (relay_index - 1))
            elif command == 0x21:  # Digital Inactive (OFF)
                state &= ~(1 << (relay_index - 1))

    def mock_recv(bufsize):
        """Mock socket.recv to return appropriate responses."""
        nonlocal state, sent_commands

        last_sent = sent_commands[-1] if sent_commands else None

        if last_sent and len(last_sent) == 1 and last_sent[0] == 0x24:
            return bytes([state])
        else:
            return b'\x00'

    mock_socket = mocker.MagicMock()
    mock_socket.sendall.side_effect = mock_sendall
    mock_socket.recv.side_effect = mock_recv
    mock_socket.__enter__ = mocker.MagicMock(return_value=mock_socket)
    mock_socket.__exit__ = mocker.MagicMock(return_value=None)

    def mock_socket_factory(*args, **kwargs):
        return mock_socket

    mock_socket_class = mocker.patch("socket.socket")
    mock_socket_class.side_effect = mock_socket_factory
    mock_socket_class.return_value = mock_socket

    return mock_socket


def _make_eth008_driver(target, index, invert):
    """Helper function to create an ETH008 digital output driver with resource."""
    eth008_res = Eth008DigitalOutput(
        target,
        name=None,
        host='192.168.1.100',
        index=str(index),
        invert=invert
    )

    driver = Eth008DigitalOutputDriver(target, name=None)
    target.activate(driver)

    return driver


def test_eth008_instance(target, mocker):
    """Test that Eth008DigitalOutputDriver can be instantiated and activated."""
    mocker.patch("socket.socket")
    driver = _make_eth008_driver(target, 1, False)
    assert isinstance(driver, Eth008DigitalOutputDriver)


def test_eth008_set_true(target, mock_tcp_server):
    """Test setting ETH008 relay to True (asserted)."""
    driver = _make_eth008_driver(target, 1, False)

    driver.set(True)

    # Verify the correct command was sent (0x20 = Digital Active, 0x01 = relay 1, 0x00 = permanent)
    mock_tcp_server.sendall.assert_any_call(bytes([0x20, 0x01, 0x00]))


def test_eth008_set_false(target, mock_tcp_server):
    """Test setting ETH008 relay to False (de-asserted)."""
    driver = _make_eth008_driver(target, 2, False)

    driver.set(False)

    # Verify the correct command was sent (0x21 = Digital Inactive, 0x02 = relay 2, 0x00 = permanent)
    mock_tcp_server.sendall.assert_any_call(bytes([0x21, 0x02, 0x00]))


def test_eth008_get_true(target, mock_tcp_server):
    """Test getting ETH008 relay state when True."""
    driver = _make_eth008_driver(target, 1, False)

    # Set the relay to True first
    driver.set(True)

    # Get the state
    result = driver.get()

    assert result is True


def test_eth008_get_false(target, mock_tcp_server):
    """Test getting ETH008 relay state when False."""
    driver = _make_eth008_driver(target, 2, False)

    # Set the relay to False first
    driver.set(False)

    # Get the state
    result = driver.get()

    assert result is False


def test_eth008_invert_true(target, mock_tcp_server):
    """Test ETH008 with inversion enabled."""
    driver = _make_eth008_driver(target, 1, True)  # Invert the logic

    # When invert=True, setting True should actually set the relay to False
    driver.set(True)

    # Verify that 0x21 (Digital Inactive) was sent instead of 0x20 (Digital Active)
    mock_tcp_server.sendall.assert_any_call(bytes([0x21, 0x01, 0x00]))


def test_eth008_invert_get(target, mock_tcp_server):
    """Test getting ETH008 relay state with inversion enabled."""
    driver = _make_eth008_driver(target, 1, True)  # Invert the logic

    # Set the relay to True (which will actually set it to False due to inversion)
    driver.set(True)

    # When invert=True, get() should return the opposite of the actual state
    result = driver.get()

    # The actual relay state is False, but with inversion it should return True
    assert result is True


def test_eth008_invalid_index(target, mocker):
    """Test that invalid relay indices are handled correctly."""
    mocker.patch("socket.socket")

    driver = _make_eth008_driver(target, 9, False)  # Invalid index (must be 1-8)

    # This should raise an AssertionError due to invalid index
    with pytest.raises(AssertionError):
        driver.set(True)


def test_eth008_different_indices(target, mock_tcp_server):
    """Test that different relay indices work correctly."""
    # Test first, middle, and last relays
    # Create separate targets for each test to avoid resource conflicts
    from labgrid.target import Target
    for index in [1, 4, 8]:
        test_target = Target(name=f'Test-{index}', env=None)

        driver = _make_eth008_driver(test_target, index, False)

        # Set and get should work for all indices
        driver.set(True)
        result = driver.get()

        assert result is True
