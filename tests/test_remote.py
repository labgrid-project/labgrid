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

def test_exporter_start_coordinator_unreachable(monkeypatch, tmpdir):
    monkeypatch.setenv("LG_COORDINATOR", "coordinator.invalid")

    config = "exports.yaml"
    p = tmpdir.join(config)
    p.write(
        """
    Testport:
        NetworkSerialPort:
          host: 'localhost'
          port: 4000
    """
    )

    with pexpect.spawn(f"python -m labgrid.remote.exporter {config}", cwd=tmpdir) as spawn:
        spawn.expect("coordinator is unavailable", timeout=10)
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 100, spawn.before

def test_exporter_coordinator_becomes_unreachable(coordinator, exporter):
    coordinator.suspend_tree()

    exporter.spawn.expect(pexpect.EOF, timeout=30)
    exporter.spawn.close()
    assert exporter.exitstatus == 100

    coordinator.resume_tree()
