from labgrid.driver.tminstr.scpi_arg import *
from labgrid.driver.tminstrument import TMInstrument

ALLOWED_CHANNELS = list(range(1, 17))

# Chapter 4 CHANNELS


def check_channel(channel: int):
    if channel not in ALLOWED_CHANNELS:
        raise ValueError(f"Channel number {channel} is out of range. Valid range: 1–16 (see Chapter 4 of the manual).")


def channel_output_set(driver: TMInstrument, channel):
    """
    Selects the active output channel using CHANnel command.
    """
    channel = get_int(channel)
    check_channel(channel)
    driver.command(f"CHAN {channel}")


def channel_instrument_set(driver: TMInstrument, channel):
    """
    Selects the active output channel using INSTrument[:SELect] command.
    """
    channel = get_int(channel)
    check_channel(channel)
    driver.command(f"INST {channel}")


# Chapter 5 SYST COMMANDS


def system_beeper_immediate(driver: TMInstrument):
    """
    Immediate test of the beeper (issues a beep if functional).
    """
    driver.command("SYSTem:BEEPer:IMMediate")


def system_beeper_state_set(driver: TMInstrument, state):
    """
    Enables or disables the beeper. Allowed values: True/False
    """
    state = get_bool(state)
    driver.command(f"SYSTem:BEEPer:STATe {state}")


def system_beeper_state_get(driver: TMInstrument):
    """
    Queries the current beeper state.
    Returns: "0" or "1"
    """
    return driver.query("SYSTem:BEEPer:STATe?")


def system_error_get(driver: TMInstrument):
    """
    Returns error code and error description.
    Format: e.g., 0,"NO_ERR"
    """
    return driver.query("SYSTem:ERRor?")


def system_clear(driver: TMInstrument):
    """
    Clears the system status register.
    """
    driver.command("SYSTem:CLEar")


def system_remote_set(driver: TMInstrument):
    """
    Switches to remote control mode.
    """
    driver.command("SYSTem:REMote")


def system_local_set(driver: TMInstrument):
    """
    Switches to front panel local control mode.
    """
    driver.command("SYSTem:LOCal")


def system_remote_lock(driver: TMInstrument):
    """
    Locks the device in remote control mode (prevents LOCAL button from switching).
    """
    driver.command("SYSTem:RWLock")


def lan_ip_address_get(driver: TMInstrument) -> str:
    """
    Get current IP address of the device.
    """
    return driver.query(":SYST:COMM:LAN:CURR:ADDR?")


def lan_ip_address_set(driver: TMInstrument, ip_address: str):
    """
    Set current IP address.
    """
    ip_address = get_ip(ip_address)
    driver.command(f':SYST:COMM:LAN:CURR:ADDR "{ip_address}"')


def lan_subnet_mask_get(driver: TMInstrument) -> str:
    """
    Get current subnet mask.
    """
    return driver.query(":SYSTem:COMMunicate:LAN:CURRent:SMASk?")


def lan_subnet_mask_set(driver: TMInstrument, mask: str):
    """
    Set current subnet mask.
    """
    mask = get_ip(mask)
    driver.command(f':SYSTem:COMMunicate:LAN:CURRent:SMASk "{mask}"')


def lan_gateway_get(driver: TMInstrument) -> str:
    """
    Get current gateway address.
    """
    return driver.query("SYSTem:COMMunicate:LAN:CURRent:DGATeway?")


def lan_gateway_set(driver: TMInstrument, gateway: str):
    """
    Set current gateway address.
    """
    gateway = get_ip(gateway)
    driver.command(f'SYSTem:COMMunicate:LAN:CURRent:DGATeway "{gateway}"')


def lan_mac_address_get(driver: TMInstrument) -> str:
    """
    Get current MAC address.
    """
    return driver.query(":SYSTem:COMMunicate:LAN:MACaddress?")


def lan_dhcp_state_get(driver: TMInstrument) -> str:
    """
    Get current DHCP setting (ON or OFF).
    """
    return driver.query(":SYSTem:COMMunicate:LAN:DHCP?")


def lan_dhcp_state_set(driver: TMInstrument, enable):
    """
    Set DHCP ON (True) or OFF (False).
    """
    enable = get_bool(enable)
    driver.command(f":SYSTem:COMMunicate:LAN:DHCP {'ON' if enable else 'OFF'}")


def lan_settings_valid(driver: TMInstrument):
    """
    This command makes the LAN settings valid.
    """
    driver.command(f"SYSTem:COMMunicate:LAN:SAVE")


# Chapter 6 MEAS


def measure_current_dc_get(driver: TMInstrument):
    """
    MEASure[:SCALar]:CURRent[:DC]?
    """
    return driver.query("MEAS:CURR?")


def measure_power_dc_get(driver: TMInstrument):
    """
    MEASure[:SCALar]:POWer[:DC]?
    """
    return driver.query("MEAS:POW?")


def measure_voltage_dc_get(driver: TMInstrument):
    """
    MEASure[:SCALar]:VOLTage[:DC]?
    """
    return driver.query("MEAS:VOLT?")


def measure_temperature_get(driver: TMInstrument):
    """
    MEASure[:SCALar][:EXTernal]:TEMPerature?
    """
    return driver.query("MEAS:TEMP?")


# Chapter 7 OUTPUT


def source_state_set(driver: TMInstrument, state):
    """
    This command sets the output state of the power supply.
    """
    state = get_bool(state)
    driver.command(f"OUTP {state}")


def source_state_get(driver: TMInstrument):
    """
    This command sets the output state of the power supply.
    """
    return driver.query(f"OUTP?")


# Chapter 8 INPUT


def load_state_set(driver: TMInstrument, state):
    """
    This command sets the input state of the electronic load.
    """
    state = get_bool(state)
    driver.command(f"INP {state}")


def load_state_get(driver: TMInstrument):
    """
    This command sets the input state of the electronic load.
    """
    return driver.query(f"INP?")


def load_short_set(driver: TMInstrument, state):
    """
    This command sets the electronic load to short mode.
    """
    state = get_bool(state)
    driver.command(f"INP:SHOR {state}")


def load_reversed_get(driver: TMInstrument):
    """
    This command is used to query the connection of input terminals.
    """
    return driver.query(f"INP:REV?")


# Chapter 9 Trigger Commands
# TBD

# Chapter 10 Sense Commands


def sense_enable_set(driver: TMInstrument, state):
    """
    This command enables or disables the sense function.
    """
    state = get_bool(state)
    driver.command(f"SENS {state}")


def sense_enable_get(driver: TMInstrument):
    """
    This command check the state of the sense function.
    """
    return driver.query(f"SENS?")


def sense_filter_set(driver: TMInstrument, level):
    """
    This command sets the sense filter level.
    """
    level = get_filter_level(level)
    driver.command(f"SENS:FILT:LEV {level}")


# Chapter 11 Source Commands


def source_load_mode_set(driver: TMInstrument, mode):
    """
    This command is used to switch the source mode and load mode.
    Please switch the instrument to source mode before sending source commands.
    """
    mode = get_function_mode(mode)
    driver.command(f"SYSTem:FUNCtion {mode}")


def source_load_mode_get(driver: TMInstrument):
    """
    This command is used to query the source mode and load mode.
    """
    return driver.query(f"SYSTem:FUNCtion?")


def source_load_current_set(driver: TMInstrument, current):
    """
    This command sets the current value of the power supply/load.
    """
    # TODO: range check
    current = get_float(current)
    driver.command(f"CURR {current}")


def source_load_current_get(driver: TMInstrument):
    """
    The query form of this command gets the set current value of the power supply/load.
    """
    return driver.query(f"CURR?")


def source_current_limit_pos_set(driver: TMInstrument, limit):
    """
    This command sets the positive current limit value of the power supply.
    """
    # TODO: range check
    limit = get_float(limit)
    driver.command(f"CURR:LIM:POS {limit}")


def source_current_limit_pos_get(driver: TMInstrument):
    """
    This command gets the positive current limit value of the power supply.
    """
    return driver.query(f"CURR:LIM:POS?")


def source_current_limit_neg_set(driver: TMInstrument, limit):
    """
    This command sets negative current limit value of power supply.
    """
    # TODO: range check
    limit = get_float(limit)
    driver.command(f"CURR:LIM:NEG {limit}")


def source_current_limit_neg_get(driver: TMInstrument):
    """
    This command Gets negative current limit value of power supply.
    """
    return driver.query(f"CURR:LIM:NEG?")


def source_load_oc_protection_set(driver: TMInstrument, level):
    """
    This command sets the over-current limit of the power supply/load.
    """
    # TODO: range check
    level = get_float(level)
    driver.command(f"CURR:PROT {level}")


def source_load_oc_protection_get(driver: TMInstrument):
    """
    This command gets the over-current limit of the power supply/load.
    """
    return driver.query(f"CURR:PROT?")


def source_load_oc_protection_delay_set(driver: TMInstrument, delay):
    """
    This command sets the over-current delay time of the power supply/load.
    """
    # TODO: range check
    delay = get_float(delay)
    driver.command(f"CURR:PROT:DEL {delay}")


def source_load_oc_protection_delay_get(driver: TMInstrument):
    """
    This command gets the over-current delay time of the power supply/load.
    """
    return driver.query(f"CURR:PROT:DEL?")


def source_load_oc_protection_state_set(driver: TMInstrument, state):
    """
    This command enables or disables the over-current function.
    """
    state = get_bool(state)
    driver.command(f"CURR:PROT:STAT {'ON' if state else 'OFF'}")


def source_load_oc_protection_state_get(driver: TMInstrument):
    """
    This command returns the state the over-current function.
    """
    return driver.query(f"CURR:PROT:STAT?")


def source_voltage_set(driver: TMInstrument, voltage):
    """
    This command sets the voltage value of the power supply.
    """
    voltage = get_float(voltage)
    driver.command(f"VOLT {voltage}")


def source_voltage_get(driver: TMInstrument):
    """
    This command gets the voltage value of the power supply.
    """
    return driver.query(f"VOLT?")


# Chapter 12 Load Commands
# some commands are shared with the source subsystem


def load_resistance_set(driver: TMInstrument, resistance):
    """
    This command sets the resistance value under CR mode.
    """
    resistance = get_float(resistance)
    driver.command(f"RES {resistance}")


def load_resistance_get(driver: TMInstrument):
    """
    This command gets the resistance value under CR mode.
    """
    return driver.query(f"RES?")


def load_volt_set(driver: TMInstrument, voltage):
    """
    This command sets the input voltage value under CV mode.
    """
    voltage = get_float(voltage)
    driver.command(f"VOLT {voltage}")


def load_volt_get(driver: TMInstrument):
    """
    This command gets the input voltage value under CV mode.
    """
    return driver.query(f"VOLT?")


# Chapter 15 Battery Commands


def battery_mode_set(driver: TMInstrument, mode: str):
    """
    This command is used to set the mode of battery test: charging or discharging.
    Syntax
        BATTery:MODE <CHARge|DISCharge>
    Arguments
        CHARge|DISCharge
    """
    mode = get_battery_mode(mode)
    driver.command(f"BATTery:MODE {mode}")


def battery_mode_get(driver: TMInstrument):
    """
    This command is used to get the mode of battery test: charging or discharging.
    Syntax
        BATTery:MODE?
    """
    return driver.query(f"BATTery:MODE?")


def battery_charge_voltage_set(driver: TMInstrument, voltage):
    """
    This command is used to set the battery charging voltage value.
    Syntax
                BATTery:CHARge:VOLTage <NRf+>
    Arguments
                <MINimum-MAXimum|MINimum|MAXimum>
    """
    voltage = get_float(voltage)
    driver.command(f"BATTery:CHARge:VOLTage {voltage}")


def battery_charge_voltage_get(driver: TMInstrument):
    """
    This command is used to set the battery charging voltage value.
    Query syntax
                BATTery:CHARge:VOLTage? [MINimum|MAXimum]
    """
    return driver.query(f"BATTery:CHARge:VOLTage?")


def battery_charge_current_set(driver: TMInstrument, current):
    """
    This command is used to set the battery charging current value.
    Syntax
                BATTery:CHARge:CURRent <NRf+>
    Arguments
                <MINimum-MAXimum|MINimum|MAXimum>
    Example
                BATT:CHAR:CURR 3.0
    """
    current = get_float(current)
    driver.command(f"BATTery:CHARge:CURRent {current}")


def battery_charge_current_get(driver: TMInstrument):
    """
    This command is used to set the battery charging current value.
    Query syntax
                BATTery:CHARge:CURRent? [MINimum|MAXimum]
    """
    return driver.query(f"BATTery:CHARge:CURRent?")


def battery_discharge_voltage_set(driver: TMInstrument, voltage):
    """
    This command is used to set the battery discharge voltage value.
    Syntax
                BATTery:DISCharge:VOLTage <NRf+>
    Arguments
                <MINimum-MAXimum|MINimum|MAXimum>
    """
    voltage = get_float(voltage)
    driver.command(f"BATTery:DISCharge:VOLTage {voltage}")


def battery_discharge_voltage_get(driver: TMInstrument):
    """
    This command is used to set the battery discharge voltage value.
    Query syntax
                BATTery:DISCharge:VOLTage? [MINimum|MAXimum]
    """
    return driver.query(f"BATTery:DISCharge:VOLTage?")


def battery_discharge_current_set(driver: TMInstrument, current):
    """
    This command is used to set the battery discharge current value.
    Syntax
                BATTery:DISCharge:CURRent <NRf+>
    Arguments
                <MINimum-MAXimum|MINimum|MAXimum>
    Example
                BATT:DISC:CURR 3.0
    """
    current = get_float(current)
    driver.command(f"BATTery:DISCharge:CURRent {current}")


def battery_discharge_current_get(driver: TMInstrument):
    """
    This command is used to set the battery discharge current value.
    Query syntax
                BATTery:DISCharge:CURRent? [MINimum|MAXimum]
    """
    return driver.query(f"BATTery:DISCharge:CURRent?")


def battery_stop_voltage_set(driver: TMInstrument, voltage):
    """
    This command is used to set the voltage value for the battery test cutoff.
    Syntax
                BATTery:STOP:VOLTage <NRf+>
    Arguments
                <MINimum-MAXimum|MINimum|MAXimum>
    """
    voltage = get_float(voltage)
    driver.command(f"BATTery:STOP:VOLTage {voltage}")


def battery_stop_voltage_get(driver: TMInstrument):
    """
    This command is used to set the voltage value for the battery test cutoff.
    Query syntax
                BATTery:STOP:VOLTage? [MINimum|MAXimum]
    """
    return driver.query(f"BATTery:STOP:VOLTage?")


def battery_stop_current_set(driver: TMInstrument, current):
    """
    This command is used to set the current value of the battery test cutoff.
    Syntax
                BATTery:STOP:CURRent <NRf+>
    Arguments
                <MINimum-MAXimum|MINimum|MAXimum>
    """
    current = get_float(current)
    driver.command(f"BATTery:STOP:CURRent {current}")


def battery_stop_current_get(driver: TMInstrument):
    """
    This command is used to set the current value of the battery test cutoff.
    Query syntax
                BATTery:STOP:CURRent? [MINimum|MAXimum]
    """
    return driver.query(f"BATTery:STOP:CURRent?")


def battery_stop_capacity_set(driver: TMInstrument, capacity):
    """
    This command is used to set the capacitance value of the battery test cutoff.
    Syntax
                BATTery:STOP:CAPacity <NRf+>
    Arguments
                <MINimum-MAXimum|MINimum|MAXimum>
    """
    capacity = get_float(capacity)
    driver.command(f"BATTery:STOP:CAPacity {capacity}")


def battery_stop_capacity_get(driver: TMInstrument):
    """
    This command is used to set the capacitance value of the battery test cutoff.
    Query syntax
                BATTery:STOP:CAPacity? [MINimum|MAXimum]
    """
    return driver.query(f"BATTery:STOP:CAPacity?")


def battery_stop_time_set(driver: TMInstrument, time):
    """
    This command is used to set the battery test cutoff time.
    Syntax
                BATTery:STOP:TIME <NRf+>
    Arguments
                <MINimum-MAXimum|MINimum|MAXimum>
    Example
                BATT:SHUT:TIME 3.0
    Query syntax
                BATTery:STOP:TIME? [MINimum|MAXimum]
    """
    time = get_float(time)
    driver.command(f"BATTery:STOP:TIME {time}")


def battery_stop_time_get(driver: TMInstrument):
    """
    This command is used to set the battery test cutoff time.
    Query syntax
                BATTery:STOP:TIME? [MINimum|MAXimum]
    """
    return driver.query(f"BATTery:STOP:TIME?")


def battery_state_set(driver: TMInstrument, state):
    """
    This command enables or disables the battery function.
    Syntax
                BATTery[:STATe]
    Arguments
                <0|1|OFF|ON>
    """
    state = get_bool(state)
    driver.command(f"BATT {'ON' if state else 'OFF'}")


def battery_state_get(driver: TMInstrument):
    """
    This command enables or disables the battery function.
    Query syntax
                BATTery[:STATe]?
    """
    return driver.query(f"BATT?")


def battery_save_to_memory(driver: TMInstrument, memory):
    """
    This command saves the present battery test file into the specified memory.
    Syntax
                BATTery:SAVE <BANK>
    Arguments
                <1-10>
    Example
                BATT:SAV 1
    """
    memory = get_int(memory)
    if 1 <= memory and memory <= 10:
        driver.command(f"BATT:SAV {memory}")
    else:
        raise ValueError(f"Invalid memory ID {memory}. Valid syntax memory ID is form 1 to 10.")


def battery_load_from_memory(driver: TMInstrument, memory):
    """
    This command recalls the battery test file you saved in the specified memory location.
    Syntax
                BATTery:REC <BANK>
    Arguments
                <1-10>
    Example
                BATT:REC 1
    """
    memory = get_int(memory)
    if 1 <= memory and memory <= 10:
        driver.command(f"BATT:REC {memory}")
    else:
        raise ValueError(f"Invalid memory ID {memory}. Valid syntax memory ID is form 1 to 10.")


def battery_reset(driver: TMInstrument):
    """
    This command resets the running state of the list program to initial state.
    Syntax
                [SOURce:]BATTery:RESet
    Arguments
                None
    """
    driver.command(f"BATT:RES")
