import pytest


@pytest.fixture(scope="session")
def instrument(target):
    _modbus = target.get_driver("ModbusRTUDriver")
    return _modbus
