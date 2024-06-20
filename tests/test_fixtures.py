import os
import pexpect
import pytest

@pytest.fixture
def short_env(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
"""
targets:
  test1:
    drivers: {}
  test2:
    role: foo
    resources: {}
"""
    )
    return p

@pytest.fixture
def short_test(tmpdir):
    t = tmpdir.join("test.py")
    t.write(
"""
def test(env):
    assert True
"""
    )
    return t

def test_config(short_test):
    with pexpect.spawn(f'pytest --traceconfig {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        assert b'labgrid.pytestplugin' in spawn.before
        spawn.close()
        assert spawn.exitstatus == 0

def test_env_fixture(short_env, short_test):
    with pexpect.spawn(f'pytest --lg-env {short_env} {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_env_fixture_no_logging(short_env, short_test):
    with pexpect.spawn(f'pytest -p no:logging --lg-env {short_env} {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before

def test_env_old_fixture(short_env, short_test):
    with pexpect.spawn(f'pytest --env-config {short_env} {short_test}') as spawn:
        spawn.expect("deprecated option --env-config")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_env_env_fixture(short_env, short_test):
    env=os.environ.copy()
    env['LG_ENV'] = short_env
    with pexpect.spawn(f'pytest {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_env_with_junit(short_env, short_test, tmpdir):
    x = tmpdir.join('junit.xml')
    with pexpect.spawn(f'pytest --junitxml={x} --lg-env {short_env} {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_help(short_test):
    with pexpect.spawn(f'pytest --help {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        assert b'--lg-coordinator=COORDINATOR_ADDRESS' in spawn.before
        spawn.close()
        assert spawn.exitstatus == 0

def test_help_coordinator(short_test):
    with pexpect.spawn(f'pytest --lg-coordinator=127.0.0.1:20408 --help {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_log_without_capturing(short_env, short_test, tmpdir):
    with pexpect.spawn(f'pytest -vv -s --lg-env {short_env} {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        print(spawn.before)
        assert spawn.exitstatus == 0
