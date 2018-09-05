def get_channel_info(driver, channel):
    info = {}
    info['SELECTED'] = driver.get_str("SELect:CH%i?" % channel).strip()
    info['BWLIMIT'] = driver.get_str(":CH%i:BANdwidth?" % channel).strip()
    info['COUPLING'] = driver.get_str(":CH%i:COUPling?" % channel).strip()
    info['INVERT'] = driver.get_str(":CH%i:INVert?" % channel).strip()
    info['POSITION'] = driver.get_decimal(":CH%i:POSition?" % channel)
    info['PROBE'] = driver.get_decimal(":CH%i:PRObe?" % channel)
    info['SCALE'] = driver.get_decimal(":CH%i:SCAle?" % channel)
    return info

def get_channel_values(driver, channel):
    driver.command(":MEASUrement:IMMed:SOUrce1 CH%i" % channel)
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
