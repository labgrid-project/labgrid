import os
import warnings
import pytest

from .. import Environment
from ..consoleloggingreporter import ConsoleLoggingReporter
from ..util.helper import processwrapper
from ..logging import StepFormatter, StepLogger


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    StepLogger.start()

    logging = config.pluginmanager.getplugin('logging-plugin')
    logging.log_cli_handler.setFormatter(StepFormatter())
    logging.log_file_handler.setFormatter(StepFormatter())

    config.addinivalue_line("markers",
                            "lg_feature: marker for labgrid feature flags")
    lg_log = config.option.lg_log
    if lg_log:
        ConsoleLoggingReporter(lg_log)
    env_config = config.option.env_config
    lg_env = config.option.lg_env
    lg_coordinator = config.option.lg_coordinator

    if lg_env is None:
        if env_config is not None:
            warnings.warn(pytest.PytestWarning(
                "deprecated option --env-config (use --lg-env instead)",
                __file__))
            lg_env = env_config

    env = None
    if lg_env is None:
        lg_env = os.environ.get('LG_ENV')
    if lg_env is not None:
        env = Environment(config_file=lg_env)
        if lg_coordinator is not None:
            env.config.set_option('crossbar_url', lg_coordinator)
    config._labgrid_env = env

    processwrapper.enable_logging()

@pytest.hookimpl()
def pytest_collection_modifyitems(config, items):
    """This function matches function feature flags with those found in the
    environment and disables the item if no match is found"""
    env = config._labgrid_env

    if not env:
        return

    have_feature = env.get_features() | env.get_target_features()

    for item in items:
        want_feature = set()

        for marker in item.iter_markers("lg_feature"):
            arg = marker.args[0]
            if isinstance(arg, str):
                want_feature.add(arg)
            elif isinstance(arg, list):
                want_feature.update(arg)
            else:
                raise Exception("Unsupported feature argument type")
        missing_feature = want_feature - have_feature
        if missing_feature:
            if len(missing_feature) == 1:
                skip = pytest.mark.skip(
                    reason=f'Skipping because feature "{missing_feature}" is not supported'
                )
            else:
                skip = pytest.mark.skip(
                    reason=f'Skipping because features "{missing_feature}" are not supported'
                )
            item.add_marker(skip)
