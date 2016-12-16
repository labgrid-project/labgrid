import pytest

from .. import Environment

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
    return Environment(request.config.option.env_config)

@pytest.fixture('session')
def target(request, env):
    """Return the default target `main` configured in the supplied
    configuration file."""
    return env.get_target()
