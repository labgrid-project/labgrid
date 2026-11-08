from unittest.mock import Mock

import pytest

pytest.importorskip('telnetlib3')

from labgrid import Target
from labgrid.driver import ExecutionError, WTIPowerDriver
from labgrid.protocol import PowerProtocol, ResetProtocol
from labgrid.resource import NetworkPowerPort


@pytest.fixture
def power(monkeypatch):
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    monkeypatch.setattr('telnetlib3.Telnet', Mock(return_value=connection))
    target = Target('test')
    NetworkPowerPort(target, 'port', model='wti', host='localhost', index=3)
    driver = WTIPowerDriver(target, 'power', password='secret')
    target.activate(driver)
    yield driver, connection
    target.cleanup()


@pytest.mark.parametrize('prompt', [b'NPS> ', b'IPS> ', b'NBB> '])
@pytest.mark.parametrize('state', [True, False])
def test_set_and_get(power, prompt, state):
    driver, connection = power
    assert isinstance(driver, (PowerProtocol, ResetProtocol))
    table = b'1 | other ON | OFF |\r\n3 | target | ' + (b'ON' if state else b'OFF') + b' |\r\n'
    connection.expect.side_effect = [(0, None, prompt), (0, None, prompt), (0, None, table + prompt)]
    (driver.on if state else driver.off)()
    assert [c.args[0] for c in connection.write.call_args_list] == [
        b'secret\r\n', b'/On 3\r\n' if state else b'/Off 3\r\n', b'/S\r\n']
    connection.expect.side_effect = [(0, None, prompt), (0, None, table + prompt)]
    assert driver.get() == state


@pytest.mark.parametrize('table', [b'13 | wrong outlet | ON |\r\n', b'3 | target | UNKNOWN |\r\n',
                                   b'3 | one | ON |\r\n3 | two | OFF |\r\n'])
def test_bad_status(power, table):
    driver, connection = power
    connection.expect.side_effect = [(0, None, b'NPS> '), (0, None, table + b'NPS> ')]
    with pytest.raises(ExecutionError, match='status'):
        driver.get()


def test_rejected_command(power):
    driver, connection = power
    connection.expect.side_effect = [(0, None, b'NPS> '), (0, None, b'Invalid command\r\nNPS> '),
                                     (0, None, b'3 | target | OFF |\r\nNPS> ')]
    with pytest.raises(ExecutionError, match='requested state'):
        driver.on()


def test_prompt_timeout(power):
    driver, connection = power
    connection.expect.return_value = (-1, None, b'Password:')
    with pytest.raises(ExecutionError, match='prompt'):
        driver.get()


def test_disconnect(power):
    driver, connection = power
    connection.expect.side_effect = EOFError
    with pytest.raises(ExecutionError, match='connection failed'):
        driver.get()
    connection.__exit__.assert_called_once()


@pytest.mark.parametrize('index', [0, 9])
def test_invalid_index(index):
    target = Target('test')
    NetworkPowerPort(target, 'port', model='wti', host='localhost', index=index)
    with pytest.raises(ValueError, match='index'):
        WTIPowerDriver(target, 'power')


def test_cycle(power, monkeypatch):
    driver, _ = power
    actions = []
    monkeypatch.setattr(driver, '_request', lambda value: actions.append(value))
    monkeypatch.setattr('labgrid.driver.wtipowerdriver.time.sleep', lambda delay: actions.append(delay))
    driver.cycle()
    assert actions == [False, 2.0, True]
