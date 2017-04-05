import pytest

from .. import Environment


# pylint: disable=redefined-outer-name


def pytest_addoption(parser):
    group = parser.getgroup('labgrid')
    group.addoption(
        '--env-config',
        action='store',
        dest='env_config',
        help='labgrid environment config file (deprecated).'
    )
    group.addoption(
        '--lg-env',
        action='store',
        dest='lg_env',
        help='labgrid environment config file.'
    )
    group.addoption(
        '--lg-coordinator',
        action='store',
        dest='lg_coordinator',
        metavar='CROSSBAR_URL',
        help='labgrid coordinator websocket URL.'
    )


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
                __file__
            )
            lg_env = env_config

    if lg_env is None:
        pytest.skip("missing environment config (use --lg-env)")
    env = Environment(config_file=lg_env)
    if lg_coordinator is not None:
        env.config.set_option('crossbar_url', lg_coordinator)
    yield env
    env.cleanup()


@pytest.fixture('session')
def target(env):
    """Return the default target `main` configured in the supplied
    configuration file."""
    target = env.get_target()
    return target
