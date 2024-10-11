def test_stick_plugin(target):
    sdmux = target.get_driver("USBSDMuxDriver")
    sdmux.set_mode("dut")
    sdmux.set_mode("host")
