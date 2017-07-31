import os
import pytest
import subprocess

from .. import Environment

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


@pytest.fixture('session')
def env(request):
    """Return the environment configured in the supplied configuration file.
    It contains the targets contained in the configuration file.
    """
    env_config = request.config.option.env_config
    lg_env = request.config.option.lg_env
    lg_coordinator = request.config.option.lg_coordinator

    if lg_env is None:
        if env_config is not None:
            request.config.warn(
                'LG-C1',
                "deprecated option --env-config (use --lg-env instead)",
                __file__)
            lg_env = env_config

    if lg_env is None:
        pytest.skip("missing environment config (use --lg-env)")
    env = Environment(config_file=lg_env)
    if lg_coordinator is not None:
        env.config.set_option('crossbar_url', lg_coordinator)

    if pytest.config.pluginmanager.hasplugin('junitxml'):
        my_junit = getattr(pytest.config, '_xml', None)

        if my_junit:
            my_junit.add_global_property('ENV_CONFIG', env.config_file)
            targets = list(env.config.get_targets().keys())
            my_junit.add_global_property('TARGETS', targets)

            for target, config in env.config.get_targets().items():
                try:
                    remote_name = config['resources']['RemotePlace']['name']
                    my_junit.add_global_property(
                        'TARGET_{}_REMOTE'.format(target.upper()), remote_name)
                except KeyError:
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


@pytest.fixture('session')
def target(env):
    """Return the default target `main` configured in the supplied
    configuration file."""
    target = env.get_target()
    return target
