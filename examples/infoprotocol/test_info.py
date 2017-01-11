def test_ip_info(info, capsys):
    res = info.get_ip()
    assert res != ""
    with capsys.disabled():
        print("\nIP-Adress: {}".format(res))


def test_hostname_info(info, capsys):
    res = info.get_hostname()
    assert res != ""
    with capsys.disabled():
        print("\nHostname: {}".format(res))
