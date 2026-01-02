import os
import copy
import logging
from typing import List, Optional

import pytest
from _pytest.logging import LoggingPlugin

from .. import Environment
from ..consoleloggingreporter import ConsoleLoggingReporter
from ..util.helper import processwrapper
from ..logging import CONSOLE, StepFormatter, StepLogger
from ..exceptions import NoStrategyFoundError

LABGRID_ENV_KEY = pytest.StashKey[Optional[Environment]]()


@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config: pytest.Config) -> None:
    def set_cli_log_level(level: int) -> None:
        nonlocal config

        try:
            current_level = config.getoption("log_cli_level") or config.getini("log_cli_level")
        except ValueError:
            return
        print(f"current_level: {current_level}")

        if isinstance(current_level, str):
            s = current_level.strip()
            try:
                current_level_val: Optional[int] = int(s)
            except ValueError:
                v = logging.getLevelName(s.upper())
                current_level_val = v if isinstance(v, int) else None
        elif isinstance(current_level, int):
            current_level_val = current_level
        else:
            current_level_val = None

        assert current_level_val is None or isinstance(current_level_val, int), \
            "unexpected type of current log level"

        # If no level was set previously (via ini or cli) or current_level is
        # less verbose than level, set to new level.
        if current_level_val is None or level < current_level_val:
            config.option.log_cli_level = str(level)

    verbosity = config.getoption("verbose")
    assert isinstance(verbosity, int), "unexpected verbosity option type"
    if verbosity > 3: # enable with -vvvv
        set_cli_log_level(logging.DEBUG)
    elif verbosity > 2: # enable with -vvv
        set_cli_log_level(CONSOLE)
    elif verbosity > 1: # enable with -vv
        set_cli_log_level(logging.INFO)


def configure_pytest_logging(config: pytest.Config, plugin: LoggingPlugin) -> None:
    if (add_color_level := getattr(plugin.log_cli_handler.formatter, "add_color_level", None)) is not None:
        add_color_level(CONSOLE, "blue")
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
def pytest_configure(config: pytest.Config) -> None:
    StepLogger.start()
    config.add_cleanup(StepLogger.stop)

    logging_plugin = config.pluginmanager.getplugin('logging-plugin')
    if logging_plugin:
        assert isinstance(logging_plugin, LoggingPlugin), "unexpected type of logging-plugin"
        configure_pytest_logging(config, logging_plugin)

    config.addinivalue_line("markers",
                            "lg_feature: skip tests on envs/targets without given labgrid feature flags")
    config.addinivalue_line("markers",
                            "lg_xfail_feature: mark tests xfail on envs/targets with given labgrid feature flag")

    lg_log = config.option.lg_log
    if lg_log:
        ConsoleLoggingReporter(lg_log)
    lg_env = config.option.lg_env
    lg_coordinator = config.option.lg_coordinator

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
def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: List[pytest.Item]) -> None:
    """This function matches function feature flags with those found in the
    environment and disables the item if no match is found"""
    del session  # unused

    env = config.stash[LABGRID_ENV_KEY]

    if not env:
        return

    have_feature = env.get_features() | env.get_target_features()

    for item in items:
        # pytest.mark.lg_feature
        lg_feature_signature = "pytest.mark.lg_feature(features: str | list[str])"
        want_feature = set()

        for marker in item.iter_markers("lg_feature"):
            if len(marker.args) != 1 or marker.kwargs:
                raise pytest.UsageError(f"Unexpected number of args/kwargs for {lg_feature_signature}")
            elif isinstance(marker.args[0], str):
                want_feature.add(marker.args[0])
            elif isinstance(marker.args[0], list):
                want_feature.update(marker.args[0])
            else:
                raise pytest.UsageError(f"Unsupported 'features' argument type ({type(marker.args[0])}) for {lg_feature_signature}")

        missing_feature = want_feature - have_feature
        if missing_feature:
            reason = f'unsupported feature(s): {", ".join(missing_feature)}'
            item.add_marker(pytest.mark.skip(reason=reason))

        # pytest.mark.lg_xfail_feature
        lg_xfail_feature_signature = "pytest.mark.lg_xfail_feature(feature: str, *, **xfail_kwargs), xfail_kwargs as pytest.mark.xfail expects them"
        for marker in item.iter_markers("lg_xfail_feature"):
            if len(marker.args) != 1:
                raise pytest.UsageError(f"Unexpected number of arguments for {lg_xfail_feature_signature}")
            elif not isinstance(marker.args[0], str):
                raise pytest.UsageError(f"Unsupported 'feature' argument type {type(marker.args[0])} for {lg_xfail_feature_signature}")
            if "condition" in marker.kwargs:
                raise pytest.UsageError(f"Unsupported 'condition' argument for {lg_xfail_feature_signature}")

            kwargs = copy.copy(marker.kwargs)
            reason = kwargs.pop("reason", marker.args[0])
            item.add_marker(
                pytest.mark.xfail(
                    condition=marker.args[0] in have_feature,
                    reason=reason,
                    **kwargs,
                )
            )

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item) -> None:
    """
    Skip test if one of the targets uses a strategy considered broken.
    """
    # Before any fixtures run for the test, check if the session-scoped strategy fixture was
    # requested (might have been executed already for a prior test). If that's the case and the
    # strategy is broken, skip the test.
    if "strategy" in item.fixturenames:
        env = item.config.stash[LABGRID_ENV_KEY]
        # skip test even if only one of the targets in the env has a broken strategy
        for target_name in env.config.get_targets():
            target = env.get_target(target_name)
            try:
                strategy = target.get_strategy()
                if strategy.broken:
                    pytest.skip(f"{strategy.__class__.__name__} is in broken state")
            except NoStrategyFoundError:
                pass
