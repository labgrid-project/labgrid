import asyncio

from labgrid.resource import SNMPEthernetPort


def test_instance(target):
    # SNMPEthernetPort should be called with a running event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        s = SNMPEthernetPort(target, 'port-1', switch='dummy-switch', interface='1')
        assert (isinstance(s, SNMPEthernetPort))
    finally:
        loop.close()
