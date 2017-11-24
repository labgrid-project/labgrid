import pytest
import stat
import os
from labgrid.consoleloggingreporter import ConsoleLoggingReporter

@pytest.fixture(scope='function')
def consolelogger(tmpdir):
    ConsoleLoggingReporter.start(str(tmpdir))
    yield
    ConsoleLoggingReporter.stop()

def test_consoleloggingreporter_output_with_name(consolelogger, serial_driver, tmpdir):
    def return_test(self, size=1, timeout=0.0):
        return b"test"
    serial_driver.serial.in_waiting = 4
    serial_driver.serial.read = return_test
    serial_driver.read()
    assert tmpdir.join("console_Test_serial").readlines()[-1] == 'test'

def test_consoleloggingreporter_output_without_name(consolelogger, serial_driver_no_name, tmpdir):
    def return_test(self, size=1, timeout=0.0):
        return b"test"
    serial_driver_no_name.serial.in_waiting = 4
    serial_driver_no_name.serial.read = return_test
    serial_driver_no_name.read()
    assert tmpdir.join("console_Test").readlines()[-1] == 'test'

def test_consoleloggingreporter_dir_not_writeable(consolelogger, serial_driver, tmpdir):
    os.chmod(str(tmpdir), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    def return_test(self, size=1, timeout=0.0):
        return b"test"
    serial_driver.serial.in_waiting = 4
    serial_driver.serial.read = return_test
    serial_driver.read()
