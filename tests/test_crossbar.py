import os
import re
import time

import pytest
import pexpect

psutil = pytest.importorskip("psutil")

pytestmark = pytest.mark.crossbar

def suspend_tree(pid):
    main = psutil.Process(pid)
    main.suspend()
    for child in main.children(recursive=True):
        child.suspend()

def resume_tree(pid):
    main = psutil.Process(pid)
    main.resume()
    for child in main.children(recursive=True):
        child.resume()

def test_startup(crossbar):
    pass

@pytest.fixture(scope='function')
def place(crossbar):
    with pexpect.spawn('python -m labgrid.remote.client -p test create') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test set-tags board=bar') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    yield

    with pexpect.spawn('python -m labgrid.remote.client -p test delete') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

@pytest.fixture(scope='function')
def place_acquire(place, exporter):
    with pexpect.spawn('python -m labgrid.remote.client -p test add-match "*/Testport/*"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    yield

    with pexpect.spawn('python -m labgrid.remote.client -p test release') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_connect_error():
    with pexpect.spawn('python -m labgrid.remote.client -x ws://127.0.0.1:20409/ws places') as spawn:
        spawn.expect("Could not connect to coordinator")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 1, spawn.before.strip()

def test_connect_timeout(crossbar):
    suspend_tree(crossbar.pid)
    try:
        with pexpect.spawn('python -m labgrid.remote.client places') as spawn:
            spawn.expect("connection closed during setup")
            spawn.expect(pexpect.EOF)
            spawn.close()
            assert spawn.exitstatus == 1, spawn.before.strip()
    finally:
        resume_tree(crossbar.pid)
        pass

def test_place_show(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test show') as spawn:
        spawn.expect("Place 'test':")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_place_alias(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test add-alias foo') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p foo del-alias foo') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_place_comment(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test set-comment my comment') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test show') as spawn:
        spawn.expect("Place 'test':")
        spawn.expect(" comment: my comment")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_place_match(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test add-match "e1/g1/r1" "e2/g2/*"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test del-match "e1/g1/r1"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test show') as spawn:
        spawn.expect(" matches:")
        spawn.expect(" e2/g2/*")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_place_match_duplicates(place):
    # first given match should succeed, second should be skipped
    matches = (
        ("e1/g1/r1", "e1/g1/r1"),
        ("e1/g1/r1/n1", "e1/g1/r1/n1"),
        ("e1/g1/r1/n1", "e1/g1/r1"),
        ("e1/g1/r1", "e1/g1/r1/n1"),
    )
    for match in matches:
        with pexpect.spawn(f'python -m labgrid.remote.client -p test add-match "{match[0]}" "{match[1]}"') as spawn:
            spawn.expect(f"pattern '{match[1]}' exists, skipping")
            spawn.expect(pexpect.EOF)
            spawn.close()
            assert spawn.exitstatus == 0, spawn.before.strip()

        with pexpect.spawn(f'python -m labgrid.remote.client -p test del-match "{match[0]}"') as spawn:
            spawn.expect(pexpect.EOF)
            spawn.close()
            assert spawn.exitstatus == 0, spawn.before.strip()

def test_place_acquire(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client who') as spawn:
        spawn.expect(".*test.*")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test release') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_place_acquire_enforce(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test add-match does/not/exist') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect("Match does/not/exist has no matching remote resource")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus != 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test acquire --allow-unmatched') as spawn:
        spawn.expect("acquired place test")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test release') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_place_acquire_broken(place, exporter):
    with pexpect.spawn('python -m labgrid.remote.client -p test add-match "*/Broken/*"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect('failed to acquire place test')
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 1, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test show') as spawn:
        spawn.expect("'broken': 'start failed'")
        spawn.expect(pexpect.EOF)
        spawn.close()
        print(spawn.before.decode())
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_place_release_from(monkeypatch, place, exporter):
    user = "test-user"
    host = "test-host"
    monkeypatch.setenv("LG_USERNAME", user)
    monkeypatch.setenv("LG_HOSTNAME", host)

    # Acquire place
    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    # Ensure place is acquired by user
    with pexpect.spawn('python -m labgrid.remote.client who') as spawn:
        spawn.expect(f"{user}\\s+{host}\\s+test")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    # Use release-from to release for a different user
    with pexpect.spawn('python -m labgrid.remote.client -p test release-from foo/bar') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    # Ensure place is still acquired by this user
    with pexpect.spawn('python -m labgrid.remote.client who') as spawn:
        spawn.expect(f"{user}\\s+{host}\\s+test")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    # Use release-from to release place for this user
    with pexpect.spawn(f'python -m labgrid.remote.client -p test release-from {host}/{user}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    # Ensure place is still no longer acquired
    with pexpect.spawn('python -m labgrid.remote.client who') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        before = spawn.before.decode("utf-8").strip()
        assert user not in before and not host in before, before

def test_place_add_no_name(crossbar):
    with pexpect.spawn('python -m labgrid.remote.client create') as spawn:
        spawn.expect("missing place name")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus != 0, spawn.before.strip()

def test_place_del_no_name(crossbar):
    with pexpect.spawn('python -m labgrid.remote.client delete') as spawn:
        spawn.expect("deletes require an exact place name")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus != 0, spawn.before.strip()

def test_remoteplace_target(place_acquire, tmpdir):
    from labgrid.environment import Environment
    p = tmpdir.join("config.yaml")
    p.write(
        """
    targets:
      test1:
        role: foo
        resources:
          RemotePlace:
            name: test
    """
    )
    e = Environment(str(p))
    t = e.get_target("test1")
    t.await_resources(t.resources)

    remote_place = t.get_resource("RemotePlace")
    assert remote_place.tags == {"board": "bar"}

def test_remoteplace_target_without_env(request, place_acquire):
    from labgrid import Target
    from labgrid.resource import RemotePlace

    t = Target(request.node.name)
    remote_place = RemotePlace(t, name="test")
    assert remote_place.tags == {"board": "bar"}

def test_resource_conflict(place_acquire, tmpdir):
    with pexpect.spawn('python -m labgrid.remote.client -p test2 create') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test2 add-match "*/Testport/*"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test2 acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus != 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test2 delete') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_reservation(place_acquire, tmpdir):
    with pexpect.spawn('python -m labgrid.remote.client reserve --shell board=bar name=test') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        m = re.search(rb"^export LG_TOKEN=(\S+)$", spawn.before.replace(b'\r\n', b'\n'), re.MULTILINE)
        assert m is not None, spawn.before.strip()
        token = m.group(1)

    env = os.environ.copy()
    env['LG_TOKEN'] = token.decode('ASCII')

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        assert b'waiting' in spawn.before, spawn.before.strip()
        assert token in spawn.before, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test release') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        assert b'allocated' in spawn.before, spawn.before.strip()
        assert token in spawn.before, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        assert b'allocated' in spawn.before, spawn.before.strip()
        assert token in spawn.before, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p + acquire', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p + show', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert token in spawn.before, spawn.before.strip()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p + release', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        assert b'allocated' in spawn.before, spawn.before.strip()
        assert token in spawn.before, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client cancel-reservation', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        assert token not in spawn.before, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_exporter_timeout(place, exporter):
    with pexpect.spawn('python -m labgrid.remote.client resources') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        assert b'/Testport/NetworkSerialPort' in spawn.before

    # lock resources ensure cleanup is needed
    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    suspend_tree(exporter.pid)
    try:
        time.sleep(30)

        # the unresponsive exporter should be kicked by now
        with pexpect.spawn('python -m labgrid.remote.client resources') as spawn:
            spawn.expect(pexpect.EOF)
            spawn.close()
            assert spawn.exitstatus == 0, spawn.before.strip()
            assert b'/Testport/NetworkSerialPort' not in spawn.before
    finally:
        resume_tree(exporter.pid)

    # the exporter should quit by itself now
    time.sleep(5)

    assert not exporter.isalive()
    assert exporter.exitstatus == 100

    with pexpect.spawn('python -m labgrid.remote.client -p test release') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_reservation_custom_config(place, exporter, tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
    """
    targets:
      test1:
        role: foo
        resources:
          RemotePlace:
            name: test
    """
    )
    with pexpect.spawn(f'python -m labgrid.remote.client -c {p} reserve --wait --shell board=bar name=test') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        m = re.search(rb"^export LG_TOKEN=(\S+)$", spawn.before.replace(b'\r\n', b'\n'), re.MULTILINE)
        s = re.search(rb"^Selected role$", spawn.before.replace(b'\r\n', b'\n'), re.MULTILINE)
        assert m is not None, spawn.before.strip()
        assert s is None, spawn.before.strip()
        token = m.group(1)

    env = os.environ.copy()
    env['LG_TOKEN'] = token.decode('ASCII')

    with pexpect.spawn(f'python -m labgrid.remote.client -c {p} -p + lock', env=env) as spawn:
        spawn.expect("acquired place test")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn(f'python -m labgrid.remote.client -c {p} -p + release', env=env) as spawn:
        spawn.expect("released place test")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_reservation_custom_config_template(place, exporter, tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
    """
    targets:
      test1:
        role: foo
        resources:
          RemotePlace:
            name: !template $LG_PLACE
        drivers:
        - ManualPowerDriver: {}
    """
    )
    env = os.environ.copy()
    env['LG_PLACE'] = '+'
    with pexpect.spawn(f'python -m labgrid.remote.client -c {p} reserve --wait --shell board=bar name=test', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        m = re.search(rb"^export LG_TOKEN=(\S+)$", spawn.before.replace(b'\r\n', b'\n'), re.MULTILINE)
        s = re.search(rb"^Selected role$", spawn.before.replace(b'\r\n', b'\n'), re.MULTILINE)
        assert m is not None, spawn.before.strip()
        assert s is None, spawn.before.strip()
        token = m.group(1)

    env['LG_TOKEN'] = token.decode('ASCII')

    with pexpect.spawn(f'python -m labgrid.remote.client -c {p} lock', env=env) as spawn:
        spawn.expect("acquired place test")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn(f'python -m labgrid.remote.client -c {p} power get', env=env) as spawn:
        spawn.expect("Selected role test1 from configuration file")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 2, spawn.before.strip()

    with pexpect.spawn(f'python -m labgrid.remote.client -c {p} release', env=env) as spawn:
        spawn.expect("released place test")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

def test_same_name_resources(place, exporter, tmpdir):
    with pexpect.spawn('python -m labgrid.remote.client -p test add-named-match "testhost/Many/NetworkService" "samename"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test add-named-match "testhost/Many/NetworkSerialPort" "samename"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test env') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        assert "NetworkService".encode("utf-8") in spawn.before.replace(b'\r\n', b'\n'), spawn.before.strip()
        assert "NetworkSerialPort".encode("utf-8") in spawn.before.replace(b'\r\n', b'\n'), spawn.before.strip()

    with pexpect.spawn('python -m labgrid.remote.client -p test release') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
