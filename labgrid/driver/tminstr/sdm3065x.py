from labgrid.driver.tminstrument import TMInstrument

VOLTAGE_RANGES = ["AUTO", "MIN", "MAX", "200mV", "2V", "20V", "200V", "1000V", "750V"]
CURRENT_RANGES = ["AUTO", "MIN", "MAX", "200uA", "2mA", "20mA", "2A", "10A"]
RESISTANCE_RANGES = ["AUTO", "MIN", "MAX"]
CAPACITANCE_RANGES = ["AUTO", "MIN", "MAX", "2nF", "20nF", "200nF", "2uF ", "20uF", "200uF", "2mF", "20mF", "100mF"]
PROBE_TYPES = ["RTD", "THER"]
RTD_TYPES = ["PT100"]
THC_TYPES = ["BITS90", "EITS90", "JITS90", "KITS90", "NITS90", "RITS90", "SITS90", "TITS90", "DEFault", "DEF"]


def check_voltage_range(value: str):
    if value not in VOLTAGE_RANGES:
        raise ValueError(f"Invalid range '{value}'. Must be one of: {VOLTAGE_RANGES}")


def check_current_range(value: str):
    if value not in CURRENT_RANGES:
        raise ValueError(f"Invalid range '{value}'. Must be one of: {CURRENT_RANGES}")


def check_resistance_range(value: str):
    if value not in RESISTANCE_RANGES:
        raise ValueError(f"Invalid range '{value}'. Must be one of: {RESISTANCE_RANGES}")


def check_capacitance_range(value: str):
    if value not in CAPACITANCE_RANGES:
        raise ValueError(f"Invalid range '{value}'. Must be one of: {CAPACITANCE_RANGES}")


def check_temperature(probe_type: str, type: str):
    if probe_type not in PROBE_TYPES:
        raise ValueError(f"Invalid range '{probe_type}'. Must be one of: {PROBE_TYPES}")
    if probe_type == "RTD":
        if type not in RTD_TYPES:
            raise ValueError(f"Invalid sensor type '{type}'. Must be one of: {RTD_TYPES}")
    if probe_type == "THER":
        if type not in THC_TYPES:
            raise ValueError(f"Invalid sensor type '{type}'. Must be one of: {THC_TYPES}")


def measure_voltage_dc(dmm: TMInstrument, range: str = "AUTO"):
    check_voltage_range(range)
    return dmm.query(f":MEASure:VOLTage:DC? {range}")


def measure_voltage_ac(dmm: TMInstrument, range: str = "AUTO"):
    check_voltage_range(range)
    return dmm.query(f":MEASure:VOLTage:AC? {range}")


def measure_current_dc(dmm: TMInstrument, range: str = "AUTO"):
    check_current_range(range)
    return dmm.query(f":MEASure:CURRent:DC? {range}")


def measure_current_ac(dmm: TMInstrument, range: str = "AUTO"):
    check_current_range(range)
    return dmm.query(f":MEASure:CURRent:AC? {range}")


def measure_resistance(dmm: TMInstrument, range: str = "AUTO"):
    check_resistance_range(range)
    return dmm.query(f":MEASure:RESistance? {range}")


def measure_resistance_4wire(dmm: TMInstrument, range: str = "AUTO"):
    check_resistance_range(range)
    return dmm.query(f":MEASure:FRESistance? {range}")


def measure_frequency(dmm: TMInstrument):
    return dmm.query(":MEASure:FREQuency?")


def measure_period(dmm: TMInstrument):
    return dmm.query(":MEASure:PERiod?")


def measure_capacitance(dmm: TMInstrument, range: str = "AUTO"):
    check_capacitance_range(range)
    return dmm.query(f":MEASure:CAPacitance? {range}")


def measure_diode(dmm: TMInstrument):
    return dmm.query(":MEASure:DIODe?")


def measure_continuity(dmm: TMInstrument):
    return dmm.query(":MEASure:CONTinuity?")


def measure_temperature(dmm: TMInstrument, probe_type: str = "RTD", sensor_type: str = "PT100"):
    check_temperature(probe_type, sensor_type)
    return dmm.query(f":MEASure:TEMPerature? {probe_type},{sensor_type}")


def lan_get_ip_address(dmm: TMInstrument):
    return dmm.query(":SYSTem:COMMunicate:LAN:IPADdress?")


def lan_set_ip_address(dmm: TMInstrument, ip_address: str):
    dmm.command(f':SYSTem:COMMunicate:LAN:IPADdress "{ip_address}"')


def lan_get_subnet_mask(dmm: TMInstrument):
    return dmm.query(":SYSTem:COMMunicate:LAN:SMASk?")


def lan_set_subnet_mask(dmm: TMInstrument, mask: str):
    dmm.command(f':SYSTem:COMMunicate:LAN:SMASk "{mask}"')
