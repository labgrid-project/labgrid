import os
import warnings
import logging
import pytest

from .. import Environment
from ..consoleloggingreporter import ConsoleLoggingReporter
from ..util.helper import processwrapper
from ..logging import StepFormatter, StepLogger

LABGRID_ENV_KEY = pytest.StashKey[Environment]()


@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config):
    def set_cli_log_level(level):
        nonlocal config

        try:
            current_level = config.getoption("log_cli_level") or config.getini("log_cli_level")
        except ValueError:
            return
        print(f"current_level: {current_level}")

        if isinstance(current_level, str):
            try:
                current_level = int(logging.getLevelName(current_level))
            except ValueError:
                current_level = None

        # If no level was set previously (via ini or cli) or current_level is
        # less verbose than level, set to new level.
        if current_level is None or level < current_level:
            config.option.log_cli_level = str(level)

    verbosity = config.getoption("verbose")
    if verbosity > 3: # enable with -vvvv
        set_cli_log_level(logging.DEBUG)
    elif verbosity > 2: # enable with -vvv
        set_cli_log_level(logging.CONSOLE)
    elif verbosity > 1: # enable with -vv
        set_cli_log_level(logging.INFO)


def configure_pytest_logging(config, plugin):
    plugin.log_cli_handler.formatter.add_color_level(logging.CONSOLE, "blue")
    plugin.log_cli_handler.setFormatter(StepFormatter(
        color=config.option.lg_colored_steps,
        parent=plugin.log_cli_handler.formatter,
    ))
    plugin.log_file_handler.setFormatter(StepFormatter(
        parent=plugin.log_file_handler.formatter,
    ))

    # Might be the same formatter instance, so get a reference for both before
    # changing either
    report_formatter = plugin.report_handler.formatter
    caplog_formatter = plugin.caplog_handler.formatter

    plugin.report_handler.setFormatter(StepFormatter(parent=report_formatter))
    plugin.report_handler.setFormatter(StepFormatter(parent=caplog_formatter))

@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    StepLogger.start()
    config.add_cleanup(StepLogger.stop)

    logging_plugin = config.pluginmanager.getplugin('logging-plugin')
    if logging_plugin:
        configure_pytest_logging(config, logging_plugin)

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
            env.config.set_option('coordinator_address', lg_coordinator)
    config.stash[LABGRID_ENV_KEY] = env

    processwrapper.enable_logging()

@pytest.hookimpl()
def pytest_collection_modifyitems(config, items):
    """This function matches function feature flags with those found in the
    environment and disables the item if no match is found"""
    env = config.stash[LABGRID_ENV_KEY]

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
