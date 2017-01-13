import pytest

from ..step import steps


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    terminalreporter = config.pluginmanager.getplugin('terminalreporter')
    if terminalreporter.verbosity > 1:  # enable with -vv
        config.pluginmanager.register(StepReporter(terminalreporter))


class StepReporter:
    def __init__(self, terminalreporter):
        self.tr = terminalreporter
        steps.subscribe(self.notify)

    def notify(self, event):
        step = event.step
        indent = '  '*step.level
        self.tr.writer.line("{}{}".format(indent, event))

    @pytest.hookimpl(hookwrapper=True, trylast=True)
    def pytest_runtest_logstart(self):
        self.tr.writer.line()
        outcome = yield
        self.tr.writer.line()

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self):
        pass
