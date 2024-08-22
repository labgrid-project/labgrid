import os
import subprocess
import pytest

from ..exceptions import NoResourceFoundError, NoDriverFoundError
from ..remote.client import UserError
from ..resource.remote import RemotePlace
from ..util.ssh import sshmanager
from ..logging import DEFAULT_FORMAT
from .hooks import LABGRID_ENV_KEY

# pylint: disable=redefined-outer-name


def pytest_addoption(parser):
    group = parser.getgroup('labgrid')
    group.addoption(
        '--env-config',
        action='store',
        dest='env_config',
        help='labgrid environment config file (deprecated).')
    group.addoption(
        '--lg-env',
        action='store',
        dest='lg_env',
        help='labgrid environment config file.')
    group.addoption(
        '--lg-coordinator',
        action='store',
        dest='lg_coordinator',
        metavar='COORDINATOR_ADDRESS',
        help='labgrid coordinator HOST[:PORT].')
    group.addoption(
        '--lg-log',
        action='store',
        dest='lg_log',
        metavar='path to logfiles',
        nargs='?',
        const=".",
        help='path to store logfiles')
    group.addoption(
        '--lg-colored-steps',
        action='store_true',
        dest='lg_colored_steps',
        help='colored step reporter')
    group.addoption(
        '--lg-initial-state',
        action='store',
        dest='lg_initial_state',
        metavar='STATE_NAME',
        help='set the strategy\'s initial state (during development)')

    # We would like to use a default value hook for log_format in the logging plugin,
    # similar to the approach below:
    # https://docs.pytest.org/en/latest/how-to/writing_hook_functions.html#using-hooks-in-pytest-addoption
    parser.addini("log_format", default=DEFAULT_FORMAT, help="Default value for log_format (overwritten by labgrid)")


@pytest.fixture(scope="session")
def env(request, record_testsuite_property):
    """Return the environment configured in the supplied configuration file.
    It contains the targets contained in the configuration file.
    """
    env = request.config.stash[LABGRID_ENV_KEY]

    if not env:
        pytest.skip("missing environment config (use --lg-env)")

    record_testsuite_property('ENV_CONFIG', env.config_file)
    targets = list(env.config.get_targets().keys())
    record_testsuite_property('TARGETS', targets)

    for target_name in targets:
        try:
            target = env.get_target(target_name)
        except UserError as e:
            pytest.exit(e)
        try:
            remote_place = target.get_resource(RemotePlace, wait_avail=False)
            remote_name = remote_place.name
            record_testsuite_property(
                f'TARGET_{target_name.upper()}_REMOTE', remote_name)
        except NoResourceFoundError:
            pass

    for name, path in env.config.get_paths().items():
        record_testsuite_property(f'PATH_{name.upper()}', path)
        try:
            sha = subprocess.check_output(
                "git rev-parse HEAD".split(), cwd=path, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
        except FileNotFoundError:
            continue
        record_testsuite_property(
            f'PATH_{name.upper()}_GIT_COMMIT',
            sha.decode("utf-8").strip("\n"))

    for name, image in env.config.get_images().items():
        record_testsuite_property(
            f'IMAGE_{name.upper()}', image)
        try:
            sha = subprocess.check_output(
                "git rev-parse HEAD".split(), cwd=os.path.dirname(image),
                stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
        except FileNotFoundError:
            continue
        record_testsuite_property(
            f'IMAGE_{name.upper()}_GIT_COMMIT',
            sha.decode("utf-8").strip("\n"))

    yield env
    env.cleanup()
    sshmanager.close_all()


@pytest.fixture(scope="session")
def target(env):
    """Return the default target `main` configured in the supplied
    configuration file."""
    target = env.get_target()
    if target is None:
        raise UserError("Using target fixture without 'main' target in config")

    return target


@pytest.fixture(scope="session")
def strategy(request, target):
    """Return the Strategy of the default target `main` configured in the
    supplied configuration file."""
    try:
        strategy = target.get_driver("Strategy")
    except NoDriverFoundError as e:
        pytest.exit(e)

    state = request.config.option.lg_initial_state
    if state is not None:
        strategy.force(state)

    return strategy
