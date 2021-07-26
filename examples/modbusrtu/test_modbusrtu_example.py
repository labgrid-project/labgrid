def test_modbusrtu_example(instrument):
    """
    The interface for the modbus RTU driver is a thin adapter, having same
    interface as provided by the minimalmodbus package. Therefore, for more
    infromation on how to use the labgrid modbus RTU driver, please refer to
    the minimalmodbus documentation.
    """

    uptime_register_addr = 0x107
    instrument.write_register(uptime_register_addr, 0, functioncode=6)
    value = instrument.read_register(uptime_register_addr)

    assert value <= 1
