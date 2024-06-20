import pexpect

def test_client_help():
    with pexpect.spawn('python -m labgrid.remote.client --help') as spawn:
        spawn.expect('usage')
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert spawn.signalstatus is None

def test_exporter_help():
    with pexpect.spawn('python -m labgrid.remote.exporter --help') as spawn:
        spawn.expect('usage')
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert spawn.signalstatus is None
