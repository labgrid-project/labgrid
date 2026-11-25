import logging

import pytest

from labgrid import Target
from labgrid.consoleloggingreporter import ConsoleLoggingReporter
from labgrid.driver.fake import FakeConsoleDriver
from labgrid.logging import SerialLoggingReporter
from labgrid.step import steps


@pytest.mark.parametrize('operation,payload', [
    ('read', b'boot\xff\r\n'), ('write', b'command\xff'), ('flush', b'partial\xff'),
])
def test_non_utf8_console_data(operation, payload, tmp_path, caplog, recwarn):
    target = Target('test')
    console = FakeConsoleDriver(target, 'console')
    target.activate(console)
    reporter = SerialLoggingReporter()
    ConsoleLoggingReporter.start(str(tmp_path))
    try:
        with caplog.at_level(logging.CONSOLE):
            if operation == 'write':
                console.write(payload)
            else:
                console.rxq.append(payload)
                assert console.read() == payload
                if operation == 'flush':
                    reporter.flush()
        assert any(getattr(record, 'data', None) == payload.decode('utf-8', errors='replace')
                   for record in caplog.records)
        assert not recwarn.list
        if operation != 'write':
            assert (tmp_path / 'console_test_console').read_bytes().endswith(payload)
    finally:
        steps.unsubscribe(reporter.notify)
        ConsoleLoggingReporter.stop()
        target.cleanup()
