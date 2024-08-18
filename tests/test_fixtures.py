import os
import pathlib

import pexpect
import pytest


@pytest.fixture
def short_env(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / 'config.yaml'
    p.write_text("""
targets:
  test1:
    drivers: {}
  test2:
    role: foo
    resources: {}
  main:
    drivers: {}
""")
    return p


@pytest.fixture
def short_test(tmp_path: pathlib.Path) -> pathlib.Path:
    t = tmp_path / 'test.py'
    t.write_text("""
def test(env):
    assert True
""")
    return t


def test_config(short_test: pathlib.Path) -> None:
    with pexpect.spawn(f'pytest --traceconfig {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        assert b'labgrid.pytestplugin' in spawn.before
        spawn.close()
        assert spawn.exitstatus == 0


def test_env_fixture(short_env: pathlib.Path, short_test: pathlib.Path) -> None:
    with pexpect.spawn(f'pytest --lg-env {short_env} {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0


def test_env_fixture_no_logging(short_env: pathlib.Path, short_test: pathlib.Path) -> None:
    with pexpect.spawn(f'pytest -p no:logging --lg-env {short_env} {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0, spawn.before


def test_env_env_fixture(short_env: pathlib.Path, short_test: pathlib.Path) -> None:
    env = os.environ.copy()
    env['LG_ENV'] = str(short_env)
    with pexpect.spawn(f'pytest {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0


def test_env_with_junit(short_env: pathlib.Path, short_test: pathlib.Path, tmp_path: pathlib.Path) -> None:
    x = tmp_path / 'junit.xml'
    with pexpect.spawn(f'pytest --junitxml={x} --lg-env {short_env} {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0


def test_help(short_test: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # argparse in Python >= 3.14 enables colored output by default,
    # disable that to allow argument assertions below
    monkeypatch.setenv("NO_COLOR", "1")

    with pexpect.spawn(f"pytest --help {short_test}") as spawn:
        spawn.expect(pexpect.EOF)
        assert b'--lg-coordinator=COORDINATOR_ADDRESS' in spawn.before
        spawn.close()
        assert spawn.exitstatus == 0


def test_help_coordinator(short_test: pathlib.Path) -> None:
    with pexpect.spawn(f'pytest --lg-coordinator=127.0.0.1:20408 --help {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0


def test_log_without_capturing(short_env: pathlib.Path, short_test: pathlib.Path) -> None:
    with pexpect.spawn(f'pytest -vv -s --lg-env {short_env} {short_test}') as spawn:
        spawn.expect(pexpect.EOF)
        spawn.close()
        print(spawn.before)
        assert spawn.exitstatus == 0
