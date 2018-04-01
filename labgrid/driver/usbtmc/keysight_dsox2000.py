def get_channel_info(driver, channel):
    info = {}
    info['BWLIMIT'] = driver.get_bool(":CHANnel%i:BWLimit?" % channel)
    info['COUPLING'] = driver.get_str(":CHANnel%i:COUPling?" % channel).strip()
    info['LABEL'] = driver.get_str(":CHANnel%i:LABel?" % channel)
    info['PROBE'] = driver.get_decimal(":CHANnel%i:PROBe?" % channel)
    info['PROBE:HEAD'] = driver.get_str(":CHANnel%i:PROBe:HEAD?" % channel).strip()
    info['PROBE:ID'] = driver.get_str(":CHANnel%i:PROBe:ID?" % channel).strip()
    info['PROBE:SKEW'] = driver.get_decimal(":CHANnel%i:PROBe:SKEW?" % channel)
    info['PROBE:STYPE'] = driver.get_str(":CHANnel%i:PROBe:STYPe?" % channel).strip()
    info['RANGE'] = driver.get_decimal(":CHANnel%i:RANGe?" % channel)
    info['SCALE'] = driver.get_decimal(":CHANnel%i:SCALe?" % channel)
    info['UNITS'] = driver.get_str(":CHANnel%i:UNITS?" % channel).strip()
    return info

def get_channel_values(driver, channel):
    driver.command(":MEASURE:SOURCE CHANNEL%i" % channel)
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
