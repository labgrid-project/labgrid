import os
import warnings
import logging
import pytest

from .. import Environment
from ..consoleloggingreporter import ConsoleLoggingReporter
from ..util.helper import processwrapper
from ..logging import StepFormatter, StepLogger

@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config):
    def set_cli_log_level(l):
        nonlocal config
        current_level = getattr(config.option, "log_cli_level", None)

        if isinstance(current_level, str):
            current_level = current_level.upper()
            try:
                current_level = int(getattr(logging, current_level, None))
            except ValueError:
                current_level = logging.WARNING

        if current_level is None or \
                current_level == logging.NOTSET or \
                current_level > l:
            config.option.log_cli_level = str(l)

    verbosity = config.getoption("verbose")
    if verbosity > 2: # enable with -vvv
        set_cli_log_level(logging.DEBUG)
    elif verbosity > 1: # enable with -vv
        set_cli_log_level(logging.INFO)


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    StepLogger.start()
    config.add_cleanup(StepLogger.stop)

    logging = config.pluginmanager.getplugin('logging-plugin')
    logging.log_cli_handler.setFormatter(StepFormatter(
        color=config.option.lg_colored_steps,
        parent=logging.log_cli_handler.formatter,
    ))
    logging.log_file_handler.setFormatter(StepFormatter(
        parent=logging.log_file_handler.formatter,
    ))

    # Might be the same formatter instance, so get a reference for both before
    # changing either
    report_formatter = logging.report_handler.formatter
    caplog_formatter = logging.caplog_handler.formatter

    logging.report_handler.setFormatter(StepFormatter(parent=report_formatter))
    logging.report_handler.setFormatter(StepFormatter(parent=caplog_formatter))

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
