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

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
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

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
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

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
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

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
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

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
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

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
        spawn.expect("1 skipped")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0


@pytest.mark.parametrize(
    "marker_args_str,error",
    [
        ("", "Unexpected number of args/kwargs"),
        ("'too', 'many'", "Unexpected number of args/kwargs"),
        ("{'foo': 'bar'}", "Unsupported 'features' argument type"),
    ],
    ids=["no args", "too many args", "unsupported arg type"],
)
def test_lg_feature_unexpected_args(tmpdir, env_feature_config, marker_args_str, error):
    # features do not matter here, simply generate a valid env config
    conf = env_feature_config([])
    test = tmpdir.join("test.py")
    test.write(
        f"""
import pytest

@pytest.mark.lg_feature({marker_args_str})
def test(self, env):
    assert True
"""
    )

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
        spawn.expect(error)
        spawn.expect(pexpect.EOF)
        spawn.close()
        # pytest command line usage error leads to exit code 4
        assert spawn.exitstatus == 4


def test_xfail_feature(tmpdir, env_feature_config):
    conf = env_feature_config(["test"])
    test = tmpdir.join("test.py")
    test.write(
        """
import pytest

@pytest.mark.lg_xfail_feature("test")
def test(env):
    assert False
"""
    )

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
        spawn.expect("1 xfailed")
        spawn.expect(pexpect.EOF)
    assert spawn.exitstatus == 0


def test_no_xfail_feature(tmpdir, env_feature_config):
    conf = env_feature_config([])
    test = tmpdir.join("test.py")
    test.write(
        """
import pytest

@pytest.mark.lg_xfail_feature("test")
def test(env):
    assert False
"""
    )

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
        spawn.expect("1 failed")
        spawn.expect(pexpect.EOF)
    assert spawn.exitstatus == 1


@pytest.mark.parametrize(
    "marker_args_str,error",
    [
        ("", "Unexpected number of arguments"),
        ("'too', 'many'", "Unexpected number of arguments"),
        ("{'foo': 'bar'}", "Unsupported 'feature' argument type"),
        ("'feature', condition='mycondition'", "Unsupported 'condition' argument"),
    ],
    ids=["no args", "too many args", "unsupported arg type", "unsupported condition"],
)
def test_lg_xfail_feature_unexpected_args(tmpdir, env_feature_config, marker_args_str, error):
    # features do not matter here, simply generate a valid env config
    conf = env_feature_config([])
    test = tmpdir.join("test.py")
    test.write(
        f"""
import pytest

@pytest.mark.lg_xfail_feature({marker_args_str})
def test(self, env):
    assert True
"""
    )

    with pexpect.spawn(f"pytest --lg-env {conf} {test}") as spawn:
        spawn.expect(error)
        spawn.expect(pexpect.EOF)
        spawn.close()
        # pytest command line usage error leads to exit code 4
        assert spawn.exitstatus == 4
