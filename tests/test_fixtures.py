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

def test_env_fixture(short_env, short_test):
    with pexpect.spawn('pytest --lg-env {} {}'.format(short_env,short_test)) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0


def test_env_old_fixture(short_env, short_test):
    with pexpect.spawn('pytest --env-config {} {}'.format(short_env,short_test)) as spawn:
        spawn.expect("deprecated option")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_env_env_fixture(short_env, short_test):
    env=os.environ.copy()
    env['LG_ENV'] = short_env
    with pexpect.spawn('pytest {}'.format(short_test)) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_env_with_junit(short_env, short_test, tmpdir):
    x = tmpdir.join('junit.xml')
    with pexpect.spawn('pytest --junitxml={} --env-config {} {}'.format(x,short_env,short_test)) as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        print(spawn.before)
        assert spawn.exitstatus == 0
