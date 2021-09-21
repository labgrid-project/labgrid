import pexpect


def test_autoinstall_help():
    with pexpect.spawn('python -m labgrid.autoinstall.main --help') as spawn:
        spawn.expect("usage")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_autoinstall_error_missing_autoinstall(tmpdir):
    c = tmpdir.join("config.yaml")
    c.write("""
    targets:
        test: {}
    """)
    with pexpect.spawn(f'python -m labgrid.autoinstall.main {c}') as spawn:
        spawn.expect("no 'autoinstall' section found")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 1

def test_autoinstall_error_missing_handler(tmpdir):
    c = tmpdir.join("config.yaml")
    c.write("""
    autoinstall: |
        print("foo")
    """)
    with pexpect.spawn(f'python -m labgrid.autoinstall.main {c}') as spawn:
        spawn.expect("no 'handler' definition found")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 1

def test_autoinstall_no_targets(tmpdir):
    c = tmpdir.join("config.yaml")
    c.write("""
    autoinstall:
        handler: |
            print("handler-test-output")
    """)
    with pexpect.spawn(f'python -m labgrid.autoinstall.main {c}') as spawn:
        spawn.expect("no targets found")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 1

def test_autoinstall_simple(tmpdir):
    c = tmpdir.join("config.yaml")
    c.write("""
    targets:
        test1:
            resources: {}
            drivers: {}
    autoinstall:
        handler: |
            print("handler-test-output")
    """)
    with pexpect.spawn(f'python -m labgrid.autoinstall.main --once {c}') as spawn:
        spawn.expect("handler-test-output")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

