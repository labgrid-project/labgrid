def test_usb(target):
    r = target.get_resource("MXSUSBLoader")
    assert r.devnum is not None
    assert r.busnum is not None


def test_mxs_load(target):
    bp = target.get_driver("BootstrapProtocol")
    bp.load()
