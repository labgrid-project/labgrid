import pytest

from .. import Environment


# pylint: disable=redefined-outer-name


def pytest_addoption(parser):
    group = parser.getgroup('labgrid')
    group.addoption(
        '--env-config',
        action='store',
        dest='env_config',
        help='labgrid environment config file.'
    )


@pytest.fixture('session')
def env(request):
    """Return the environment configured in the supplied configuration file.
    It contains the targets contained in the configuration file.
    """
    env_config = request.config.option.env_config
    if env_config is None:
        pytest.skip("missing environemnt config (--env-config)")
    env = Environment(config_file=request.config.option.env_config, )
    yield env
    env.cleanup()


@pytest.fixture('session')
def target(env):
    """Return the default target `main` configured in the supplied
    configuration file."""
    return env.get_target()
