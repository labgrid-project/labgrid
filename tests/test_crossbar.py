import os
import re

from importlib.util import find_spec

import pytest
import pexpect

pytestmark = pytest.mark.skipif(not find_spec("crossbar"),
                              reason="crossbar required")

def test_startup(crossbar):
    pass

@pytest.fixture(scope='function')
def place(crossbar):
    with pexpect.spawn('python -m labgrid.remote.client -p test create') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p test set-tags board=bar') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    yield

    with pexpect.spawn('python -m labgrid.remote.client -p test delete') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

@pytest.fixture(scope='function')
def place_acquire(place, exporter):
    with pexpect.spawn('python -m labgrid.remote.client -p test add-match "*/*/*"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    yield

    with pexpect.spawn('python -m labgrid.remote.client -p test release') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_place_show(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test show') as spawn:
        spawn.expect("Place 'test':")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_place_alias(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test add-alias foo') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p foo del-alias foo') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_place_comment(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test set-comment my comment') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p test show') as spawn:
        spawn.expect("Place 'test':")
        spawn.expect(" comment: my comment")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_place_match(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test add-match "e1/g1/r1" "e2/g2/*"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p test del-match "e1/g1/r1"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p test show') as spawn:
        spawn.expect(" matches:")
        spawn.expect(" e2/g2/*")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_place_aquire(place):
    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client who') as spawn:
        spawn.expect(".*test.*")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p test release') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_place_add_no_name(crossbar):
    with pexpect.spawn('python -m labgrid.remote.client create') as spawn:
        spawn.expect("missing place name")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus != 0

def test_place_del_no_name(crossbar):
    with pexpect.spawn('python -m labgrid.remote.client delete') as spawn:
        spawn.expect("deletes require an exact place name")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus != 0

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

def test_resource_conflict(place_acquire, tmpdir):
    with pexpect.spawn('python -m labgrid.remote.client -p test2 create') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p test2 add-match "*/*/*"') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p test2 acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus != 0

    with pexpect.spawn('python -m labgrid.remote.client -p test2 delete') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_reservation(place_acquire, tmpdir):
    with pexpect.spawn('python -m labgrid.remote.client reserve --shell board=bar name=test') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        m = re.search(rb"^export LG_TOKEN=(\S+)$", spawn.before.replace(b'\r\n', b'\n'), re.MULTILINE)
        assert m is not None
        token = m.group(1)

    env = os.environ.copy()
    env['LG_TOKEN'] = token.decode('ASCII')

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert b'waiting' in spawn.before
        assert token in spawn.before

    with pexpect.spawn('python -m labgrid.remote.client -p test release') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert b'allocated' in spawn.before
        assert token in spawn.before

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert b'allocated' in spawn.before
        assert token in spawn.before

    with pexpect.spawn('python -m labgrid.remote.client -p + acquire', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p + show', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert token in spawn.before
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client -p + release', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert b'allocated' in spawn.before
        assert token in spawn.before

    with pexpect.spawn('python -m labgrid.remote.client cancel-reservation', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

    with pexpect.spawn('python -m labgrid.remote.client reservations') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert token not in spawn.before

    with pexpect.spawn('python -m labgrid.remote.client -p test acquire') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
