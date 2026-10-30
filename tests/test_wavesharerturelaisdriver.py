from labgrid.resource.serialport import SerialPort
from labgrid.driver.wavesharerturelaisdriver import WaveshareRTURelaisDriver

import pytest


def test_wavesharerturelais_driver(target, mocker):
    pytest.importorskip("minimalmodbus")
    mocker.patch("serial.Serial")

    SerialPort(target, name=None, port="/dev/tty0")
    driver = WaveshareRTURelaisDriver(
        target, address=0x01, relais=3, no_channel=32, timeout=0.5, name=None
    )

    assert driver.address == 0x01
    assert driver.relais == 3
    assert driver.no_channel == 32

    target.activate(driver)

    assert driver.instrument.serial.baudrate == 115200
    assert driver.instrument.serial.timeout == 0.5
