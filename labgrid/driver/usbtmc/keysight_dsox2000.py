def get_channel_info(driver, channel):
    info = {}
    info['BWLIMIT'] = driver.get_bool(f":CHANnel{channel:d}:BWLimit?")
    info['COUPLING'] = driver.get_str(f":CHANnel{channel:d}:COUPling?").strip()
    info['LABEL'] = driver.get_str(f":CHANnel{channel:d}:LABel?")
    info['PROBE'] = driver.get_decimal(f":CHANnel{channel:d}:PROBe?")
    info['PROBE:HEAD'] = driver.get_str(f":CHANnel{channel:d}:PROBe:HEAD?").strip()
    info['PROBE:ID'] = driver.get_str(f":CHANnel{channel:d}:PROBe:ID?").strip()
    info['PROBE:SKEW'] = driver.get_decimal(f":CHANnel{channel:d}:PROBe:SKEW?")
    info['PROBE:STYPE'] = driver.get_str(f":CHANnel{channel:d}:PROBe:STYPe?").strip()
    info['RANGE'] = driver.get_decimal(f":CHANnel{channel:d}:RANGe?")
    info['SCALE'] = driver.get_decimal(f":CHANnel{channel:d}:SCALe?")
    info['UNITS'] = driver.get_str(f":CHANnel{channel:d}:UNITS?").strip()
    return info

def get_channel_values(driver, channel):
    driver.command(f":MEASURE:SOURCE CHANNEL{channel:d}")
    info = {}
    info['DUTYCYCLE'] = driver.get_decimal(":MEASURE:DUTYcycle?")
    info['FREQUENCY'] = driver.get_decimal(":MEASURE:FREQuency?")
    info['PERIOD'] = driver.get_decimal(":MEASURE:PERiod?")
    info['VMAX'] = driver.get_decimal(":MEASURE:VMAX?")
    info['VMIN'] = driver.get_decimal(":MEASURE:VMIN?")
    info['VPP'] = driver.get_decimal(":MEASURE:VPP?")
    return info

def get_screenshot_png(driver):
    driver.command(":HARDcopy:INKSaver OFF")
    return driver.query(':DISPlay:DATA? PNG, COLor', binary=True)
