import os
import subprocess
import pytest

from ..exceptions import NoResourceFoundError
from ..remote.client import UserError
from ..resource.remote import RemotePlace
from ..util.ssh import sshmanager

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
        metavar='CROSSBAR_URL',
        help='labgrid coordinator websocket URL.')
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


@pytest.fixture(scope="session")
def env(request):
    """Return the environment configured in the supplied configuration file.
    It contains the targets contained in the configuration file.
    """
    env = request.config._labgrid_env

    if not env:
        pytest.skip("missing environment config (use --lg-env)")

    if request.config.pluginmanager.hasplugin('junitxml'):
        my_junit = getattr(request.config, '_xml', None)

        if my_junit:
            my_junit.add_global_property('ENV_CONFIG', env.config_file)
            targets = list(env.config.get_targets().keys())
            my_junit.add_global_property('TARGETS', targets)

            for target_name in targets:
                target = env.get_target(target_name)
                try:
                    remote_place = target.get_resource(RemotePlace, wait_avail=False)
                    remote_name = remote_place.name
                    my_junit.add_global_property(
                        'TARGET_{}_REMOTE'.format(target_name.upper()), remote_name)
                except NoResourceFoundError:
                    pass

            for name, path in env.config.get_paths().items():
                my_junit.add_global_property('PATH_{}'.format(name.upper()), path)
                try:
                    sha = subprocess.check_output(
                        "git rev-parse HEAD".split(), cwd=path)
                except subprocess.CalledProcessError:
                    continue
                except FileNotFoundError:
                    continue
                my_junit.add_global_property(
                    'PATH_{}_GIT_COMMIT'.format(name.upper()),
                    sha.decode("utf-8").strip("\n"))

            for name, image in env.config.get_images().items():
                my_junit.add_global_property(
                    'IMAGE_{}'.format(name.upper()), image)
                try:
                    sha = subprocess.check_output(
                        "git rev-parse HEAD".split(), cwd=os.path.dirname(image))
                except subprocess.CalledProcessError:
                    continue
                except FileNotFoundError:
                    continue
                my_junit.add_global_property(
                    'IMAGE_{}_GIT_COMMIT'.format(name.upper()),
                    sha.decode("utf-8").strip("\n"))

    yield env
    env.cleanup()
    sshmanager.close_all()


@pytest.fixture(scope="session")
def target(env):
    """Return the default target `main` configured in the supplied
    configuration file."""
    try:
        target = env.get_target()
        if target is None:
            raise UserError("Using target fixture without 'main' target in config")
    except UserError as e:
        pytest.exit(e)

    return target
