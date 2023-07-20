from labgrid.resource.modbusrtu import ModbusRTU
from labgrid.driver.modbusrtudriver import ModbusRTUDriver

import pytest

def test_resource_with_minimum_argument(target):
    dut = ModbusRTU(target, name=None, port="/dev/tty1", address=10)

    assert dut.port == "/dev/tty1"
    assert dut.address == 10
    assert dut.speed == 115200
    assert dut.timeout == 0.25


def test_resource_with_non_default_argument(target):
    dut = ModbusRTU(target, name=None, port="/dev/tty1", address=10,
                    speed=9600, timeout=0.5)

    assert dut.port == "/dev/tty1"
    assert dut.address == 10
    assert dut.speed == 9600
    assert dut.timeout == 0.5


def test_driver(target, mocker):
    pytest.importorskip("minimalmodbus")
    mocker.patch('serial.Serial')

    ModbusRTU(target, name=None, port="/dev/tty0", address=10)
    driver = ModbusRTUDriver(target, name=None)

    target.activate(driver)

    assert driver.instrument.serial.baudrate == 115200
    assert driver.instrument.serial.timeout == 0.25
