import pexpect

def test_with_feature(tmpdir):
    conf = tmpdir.join("config.yaml")
    conf.write(
"""
targets:
  test1:
    features:
      - test
    drivers: {}
"""
    )
    test = tmpdir.join("test.py")
    test.write(
"""
import pytest

@pytest.mark.lg_feature("test")
def test(env):
    assert True
"""
    )

    with pexpect.spawn(f'pytest --lg-env {conf} {test}') as spawn:
        spawn.expect("1 passed")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_skip_feature(tmpdir):
    conf = tmpdir.join("config.yaml")
    conf.write(
"""
targets:
  test1:
    features:
      - test
    drivers: {}
"""
    )
    test = tmpdir.join("test2.py")
    test.write(
"""
import pytest

@pytest.mark.lg_feature("test2")
def test(env):
    assert True
"""
    )

    with pexpect.spawn(f'pytest --lg-env {conf} {test}') as spawn:
        spawn.expect("1 skipped")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_skip_feature_list(tmpdir):
    conf = tmpdir.join("config.yaml")
    conf.write(
"""
targets:
  test1:
    features:
      - test
    drivers: {}
"""
    )
    test = tmpdir.join("test2.py")
    test.write(
"""
import pytest

@pytest.mark.lg_feature(["test2", "test3"])
def test(env):
    assert True
"""
    )

    with pexpect.spawn(f'pytest --lg-env {conf} {test}') as spawn:
        spawn.expect("1 skipped")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_match_feature_list(tmpdir):
    conf = tmpdir.join("config.yaml")
    conf.write(
"""
targets:
  test1:
    features:
      - test1
      - test2
    drivers: {}
"""
    )
    test = tmpdir.join("test2.py")
    test.write(
"""
import pytest

@pytest.mark.lg_feature(["test1", "test2"])
def test(env):
    assert True
"""
    )

    with pexpect.spawn(f'pytest --lg-env {conf} {test}') as spawn:
        spawn.expect("1 passed")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_match_multi_feature_source(tmpdir):
    conf = tmpdir.join("config.yaml")
    conf.write(
"""
targets:
  test1:
    features:
      - test1
      - test2
      - test3
    drivers: {}
"""
    )
    test = tmpdir.join("test.py")
    test.write(
"""
import pytest

pytestmark = pytest.mark.lg_feature("test1")

@pytest.mark.lg_feature("test2")
class TestMulti:
    @pytest.mark.lg_feature("test3")
    def test(self, env):
        assert True
"""
    )

    with pexpect.spawn(f'pytest --lg-env {conf} {test}') as spawn:
        spawn.expect("1 passed")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

def test_skip_multi_feature_source(tmpdir):
    conf = tmpdir.join("config.yaml")
    conf.write(
"""
targets:
  test1:
    features:
      - test1
      - test3
    drivers: {}
"""
    )
    test = tmpdir.join("test.py")
    test.write(
"""
import pytest

pytestmark = pytest.mark.lg_feature("test1")

@pytest.mark.lg_feature("test2")
class TestMulti:
    @pytest.mark.lg_feature("test3")
    def test(self, env):
        assert True
"""
    )

    with pexpect.spawn(f'pytest --lg-env {conf} {test}') as spawn:
        spawn.expect("1 skipped")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
