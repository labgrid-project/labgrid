import pytest
import pexpect

@pytest.fixture
def env_feature_config(tmpdir):
    def _env_feature_config(features):
        conf = tmpdir.join("config.yaml")
        conf.write(
"""
    targets:
      test1:
        features:
"""
        )
        for feature in features:
            conf.write(f"          - {feature}\n", "a")
        if not features:
            conf.write("          {}\n", "a")

        return conf

    yield _env_feature_config

def test_with_feature(tmpdir, env_feature_config):
    conf = env_feature_config(["test"])
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

def test_skip_feature(tmpdir, env_feature_config):
    conf = env_feature_config(["test"])
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

def test_skip_feature_list(tmpdir, env_feature_config):
    conf = env_feature_config(["test"])
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

def test_match_feature_list(tmpdir, env_feature_config):
    conf = env_feature_config(["test1", "test2"])
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

def test_match_multi_feature_source(tmpdir, env_feature_config):
    conf = env_feature_config(["test1", "test2", "test3"])
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

def test_skip_multi_feature_source(tmpdir, env_feature_config):
    conf = env_feature_config(["test1", "test3"])
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
