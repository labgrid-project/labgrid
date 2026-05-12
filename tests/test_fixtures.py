import os
import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

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


@dataclass
class Scenario:
    config: Optional[str]
    test: str
    exitcode: pytest.ExitCode
    lines: List[str] = field(default_factory=list)
    outcome: Dict[str, int] = field(default_factory=dict)


COMPLETE_CONFIG = """
targets:
  main:
    resources:
      RawSerialPort:
        port: '/dev/ttyUSB0'
    drivers:
      ManualPowerDriver: {}
      SerialDriver: {}
      BareboxDriver: {}
      ShellDriver:
        prompt: 'root@\\w+:[^ ]+ '
        login_prompt: ' login: '
        username: 'root'
      BareboxStrategy: {}
  test1:
    drivers: {}
  test2:
    resources: {}
"""


@pytest.mark.parametrize(
    'scenario',
    [
        Scenario(
            config=COMPLETE_CONFIG,
            test="""
import pytest
from labgrid import Environment, Target


def test_env_fixture(env: Environment) -> None:
    assert (target1 := env.get_target('test1'))
    assert isinstance(target1, Target)
    assert env.get_target('test2')
    assert not env.get_target('test3')
""",
            exitcode=pytest.ExitCode.OK,
            outcome={'passed': 1},
        ),
        Scenario(
            config=COMPLETE_CONFIG,
            test="""
import pytest
from labgrid import Target


def test_target_fixture(target: Target) -> None:
    assert target
""",
            exitcode=pytest.ExitCode.OK,
            outcome={'passed': 1},
        ),
        Scenario(
            config=COMPLETE_CONFIG,
            test="""
import pytest
from labgrid.strategy import Strategy


def test_strategy_fixture(strategy: Strategy) -> None:
    assert strategy
""",
            exitcode=pytest.ExitCode.OK,
            outcome={'passed': 1},
        ),
        Scenario(
            config=None,
            test="""
import pytest
from labgrid import Environment, Target
from labgrid.strategy import Strategy


def test_env_fixture(env: Environment) -> None:
    del env  # unused
""",
            exitcode=pytest.ExitCode.OK,
            lines=['*SKIPPED*missing environment config*', '*1 skipped*'],
        ),
        Scenario(
            config="""
targets:
  test1:
    drivers: {}
""",
            test="""
import pytest
from labgrid import Target


def test_target_fixture(target: Target) -> None:
    assert target
""",
            exitcode=pytest.ExitCode.TESTS_FAILED,
            lines=['*UserError*Using target fixture without*', '*ERROR*'],
        ),
        Scenario(
            config="""
targets:
  main:
    drivers: {}
""",
            test="""
import pytest
from labgrid.strategy import Strategy


def test_strategy_fixture(strategy: Strategy) -> None:
    assert strategy
""",
            exitcode=pytest.ExitCode.INTERRUPTED,
            lines=['*no Strategy driver found in Target*', '*no tests ran*'],
        ),
    ],
)
def test_fixtures_with_pytester(pytester: pytest.Pytester, scenario: Scenario) -> None:
    pytester.makefile(
        '.ini',
        pytest=f"""[pytest]
python_files = test_*.py
python_functions = test_*
python_classes = Test* *_test
addopts = --strict-markers
testpaths = .
""",
    )

    if scenario.config:
        pytester.makefile('.yaml', config=scenario.config)

    pytester.makepyfile(test_sample=scenario.test)

    args = ['-s', '-vvv']
    if scenario.config:
        args += ['--lg-env', 'config.yaml']
    result = pytester.runpytest(*args)
    assert result.ret == scenario.exitcode
    if scenario.lines:
        result.stdout.fnmatch_lines(scenario.lines)
    if scenario.outcome:
        result.assert_outcomes(**scenario.outcome)
