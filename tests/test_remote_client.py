import os
import re
import time

from importlib.util import find_spec

import pytest
import pexpect

psutil = pytest.importorskip("psutil")

pytestmark = pytest.mark.skipif(not find_spec("crossbar"),
                              reason="crossbar required")

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

def test_valid_hostname(place_acquire, tmpdir):
    env = os.environ.copy()
    env['LG_USERNAME'] = 'user123'
    
    with pexpect.spawn('python -m labgrid.remote.client reserve --shell board=bar name=test', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        
def test_valid_hostname(place_acquire, tmpdir):
    env = os.environ.copy()
    env['LG_HOSTNAME'] = 'host123'
    
    with pexpect.spawn('python -m labgrid.remote.client reservations', env=env) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before.strip()
        
def test_invalid_hostname(place_acquire, tmpdir):
    env = os.environ.copy()
    env['LG_USERNAME'] = 'user/123'
    
    with pexpect.spawn('python -m labgrid.remote.client reserve --shell board=bar name=test', env=env) as spawn:
        spawn.expect("Username user/123 contains invalid character '/'")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus != 0, spawn.before.strip()
        
def test_invalid_hostname(place_acquire, tmpdir):
    env = os.environ.copy()
    env['LG_HOSTNAME'] = 'host/123'
    
    with pexpect.spawn('python -m labgrid.remote.client reservations', env=env) as spawn:
        spawn.expect("Hostname host/123 contains invalid character '/'")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus != 0, spawn.before.strip()

