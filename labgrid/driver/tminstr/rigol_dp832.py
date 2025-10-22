from labgrid.driver.tminstrument import TMInstrument

CHANNEL_LIST = [1, 2, 3]
VOLTAGE_UPPER_LIM = 32  # V
VOLTAGE_LOWER_LIM = 0  # V
CURRENT_UPPER_LIM = 3.2  # A
CURRENT_LOWER_LIM = 0  # A


def check_channel_number(channel):
    if not int(channel) in CHANNEL_LIST:
        raise ValueError(
            f"Channel index {channel} is out of expected range. For Rigol DP832 must be from list {CHANNEL_LIST}!"
        )


def check_voltage_range(value):
    if not (VOLTAGE_LOWER_LIM <= int(value) and int(value) <= VOLTAGE_UPPER_LIM):
        raise ValueError(
            f"Voltage is out of expected range. For Rigol DP832 must between {VOLTAGE_LOWER_LIM} V and {VOLTAGE_UPPER_LIM} V!"
        )


def check_current_range(value):
    if not (CURRENT_LOWER_LIM <= int(value) and int(value) <= CURRENT_UPPER_LIM):
        raise ValueError(
            f"Current is out of expected range. For Rigol DP832 must between {CURRENT_LOWER_LIM} V and {VOLTAGE_UPPER_LIM} V!"
        )


def activate(driver: TMInstrument, state, channel):
    check_channel_number(channel)
    driver.command(":OUTP CH{},{}".format(channel, "ON" if state else "OFF"))


def voltage_set(driver: TMInstrument, value, channel):
    check_channel_number(channel)
    check_voltage_range(value)
    driver.command(f":SOUR{channel}:VOLT {value}")


def voltage_get(driver: TMInstrument, channel):
    check_channel_number(channel)
    return driver.query(f":MEAS:VOLT? CH{channel}")


def voltage_preset_get(driver: TMInstrument, channel):
    check_channel_number(channel)
    return driver.query(f":SOUR{channel}:VOLT?")


def current_set(driver: TMInstrument, value, channel):
    check_channel_number(channel)
    check_current_range(value)
    driver.command(f":SOUR{channel}:CURR {value}")


def current_get(driver: TMInstrument, channel):
    check_channel_number(channel)
    return driver.query(f":MEAS:CURR? CH{channel}")


def current_preset_get(driver: TMInstrument, channel):
    check_channel_number(channel)
    return driver.query(f":SOUR{channel}:CURR?")


def state_get(driver: TMInstrument, channel):
    check_channel_number(channel)
    return driver.query(f":OUTP? CH{channel}")
