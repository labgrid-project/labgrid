from labgrid.driver.tminstrument import TMInstrument

CHANNEL_LIST = [1, 2]
VOLTAGE_UPPER_LIM = 30  # V
VOLTAGE_LOWER_LIM = 0  # V
CURRENT_UPPER_LIM = 5  # A
CURRENT_LOWER_LIM = 0  # A


def check_channel_number(channel):
    if not int(channel) in CHANNEL_LIST:
        raise ValueError(
            f"Channel index {channel} is out of expected range. For RND320-KD3305P must be from list {CHANNEL_LIST}!"
        )


def check_voltage_range(value):
    if not (VOLTAGE_LOWER_LIM <= value and value <= VOLTAGE_UPPER_LIM):
        raise ValueError(
            f"Voltage is out of expected range. For RND320-KD3305P must between {VOLTAGE_LOWER_LIM} V and {VOLTAGE_UPPER_LIM} V!"
        )


def check_current_range(value):
    if not (CURRENT_LOWER_LIM <= value and value <= CURRENT_UPPER_LIM):
        raise ValueError(
            f"Current is out of expected range. For RND320-KD3305P must between {CURRENT_LOWER_LIM} V and {VOLTAGE_UPPER_LIM} V!"
        )


def lock_front_panel(driver: TMInstrument, state: bool):
    driver.command(f"LOCK{1 if state else 0}")


def current_set(driver: TMInstrument, value: float, channel: int):
    check_channel_number(channel)
    check_current_range(value)
    driver.command(f"ISET{channel}:{value}")


def current_preset_get(driver: TMInstrument, channel: int):
    check_channel_number(channel)
    return driver.command(f"ISET{channel}?")


def current_get(driver: TMInstrument, channel: int):
    check_channel_number(channel)
    return driver.command(f"IOUT{channel}?")


def voltage_set(driver: TMInstrument, value: float, channel: int):
    check_channel_number(channel)
    check_voltage_range(value)
    driver.command(f"VSET{channel}:{value}")


def voltage_preset_get(driver: TMInstrument, channel: int):
    check_channel_number(channel)
    return driver.command(f"VSET{channel}?")


def voltage_get(driver: TMInstrument, channel: int):
    check_channel_number(channel)
    return driver.query(f"VOUT{channel}?")


def activate(driver: TMInstrument, state: bool, channel: int):
    check_channel_number(channel)
    driver.command(f":OUT{channel}:{1 if state else 0}")


def state_get(driver: TMInstrument, channel: int):
    check_channel_number(channel)
    status = driver.query("STATUS?")
    value = int(status.encode().hex())
    if int(channel) == 1:
        return (value >> 6) & 0x01
    elif int(channel) == 2:
        return (value >> 7) & 0x01
