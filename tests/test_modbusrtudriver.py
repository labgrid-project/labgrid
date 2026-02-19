from labgrid.resource.serialport import SerialPort
from labgrid.driver.modbusrtudriver import ModbusRTUDriver

import pytest



def test_driver(target, mocker):
    pytest.importorskip("minimalmodbus")
    mocker.patch('serial.Serial')

    SerialPort(target, name=None, port="/dev/tty0")
    driver = ModbusRTUDriver(target, address=10, timeout=0.5, name=None)

    assert driver.address == 10
    assert driver.timeout == 0.5

    target.activate(driver)

    assert driver.instrument.serial.baudrate == 115200
    assert driver.instrument.serial.timeout == 0.5
