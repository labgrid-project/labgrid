def get_channel_info(driver, channel):
    info = {}
    info['SELECTED'] = driver.get_str(f"SELect:CH{channel:d)}?").strip()
    info['BWLIMIT'] = driver.get_str(f":CH{channel:d}:BANdwidth?").strip()
    info['COUPLING'] = driver.get_str(f":CH{channel:d}:COUPling?").strip()
    info['INVERT'] = driver.get_str(f":CH{channel:d}:INVert?").strip()
    info['POSITION'] = driver.get_decimal(f":CH{channel:d}:POSition?")
    info['PROBE'] = driver.get_decimal(f":CH{channel:d}:PRObe?")
    info['SCALE'] = driver.get_decimal(f":CH{channel:d}:SCAle?")
    return info

def get_channel_values(driver, channel):
    driver.command(f":MEASUrement:IMMed:SOUrce1 CH{channel:d}")
    info = {}
    driver.command(":MEASUrement:IMMed:TYPe MEAN")
    info['MEAN'] = driver.get_decimal(":MEASUrement:IMMed:VALue?")
    driver.command(":MEASUrement:IMMed:TYPe FREQuency")
    info['FREQUENCY'] = driver.get_decimal(":MEASUrement:IMMed:VALue?")
    driver.command(":MEASUrement:IMMed:TYPe PK2pk")
    info['PK2PK'] = driver.get_decimal(":MEASUrement:IMMed:VALue?")
    driver.command(":MEASUrement:IMMed:TYPe MINImum")
    info['MINIMUM'] = driver.get_decimal(":MEASUrement:IMMed:VALue?")
    driver.command(":MEASUrement:IMMed:TYPe MAXImum")
    info['MAXIMUM'] = driver.get_decimal(":MEASUrement:IMMed:VALue?")
    return info

def get_screenshot_tiff(driver):
    driver.command(":hardcopy:format tiff")
    tiff = driver.query(':hardcopy start', raw=True)
    return tiff
