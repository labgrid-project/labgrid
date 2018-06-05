from labgrid.resource import SNMPEthernetPort


def test_instance(target):
    s = SNMPEthernetPort(target, 'port-1', switch='dummy-switch', interface='1')
    assert (isinstance(s, SNMPEthernetPort))
