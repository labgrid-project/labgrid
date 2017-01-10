from labgrid.protocol import InfoProtocol

def test_ip_info(target, capsys):
    command = target.get_driver(InfoProtocol)
    res = command.get_ip()
    assert res != ""
    with capsys.disabled():
        print("\nIP-Adress: {}".format(res))

def test_hostname_info(target, capsys):
    command = target.get_driver(InfoProtocol)
    res = command.get_hostname()
    assert res != ""
    with capsys.disabled():
        print("\nHostname: {}".format(res))
