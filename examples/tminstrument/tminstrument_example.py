import pytest


@pytest.fixture()
def digital_multimeter(target):
    return target.get_driver("TMInstrument", name="TM_instrument_visa-rigol-dmm")


@pytest.fixture()
def laboratory_power_supply(target):
    return target.get_driver("TMInstrument", name="TM_instrument_visa-rigol-ps")


def test_with_digital_multimeter_example(digital_multimeter):
    # Identify the device
    digital_multimeter.identify()

    # Get DC voltage reading
    assert 0.0 <= digital_multimeter.query_iterable(":MEASure:VOLTage:DC?")[0] <= 33.0
    assert 0.0 <= float(digital_multimeter.query(":MEASure:VOLTage:DC?")) <= 33.0


def test_with_laboratory_power_supply_example(laboratory_power_supply):
    # Identify the device
    laboratory_power_supply.identify()

    # Get voltage reading of channel 1
    assert 0.0 <= laboratory_power_supply.query_iterable(":MEAS:VOLT? CH1")[0] <= 33.0
    assert 0.0 <= float(laboratory_power_supply.query(":MEAS:VOLT? CH1")) <= 33.0
