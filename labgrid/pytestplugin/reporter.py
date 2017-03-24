import logging
import sys
import pytest
from _pytest.capture import safe_text_dupfile

from ..step import steps

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)


def bold(text):
    return "\033[1m{}\033[0m".format(text)

def under(text):
    return "\033[4m{}\033[0m".format(text)

@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    terminalreporter = config.pluginmanager.getplugin('terminalreporter')
    capturemanager = config.pluginmanager.getplugin('capturemanager')
    rewrite = True
    if capturemanager._method == "no":
        rewrite = False  # other output would interfere with our rewrites
    if terminalreporter.verbosity > 1:  # enable with -vv
        config.pluginmanager.register(StepReporter(terminalreporter, rewrite=rewrite))
    if terminalreporter.verbosity > 2:  # enable with -vvv
        logging.getLogger().setLevel(logging.DEBUG)


class StepReporter:
    def __init__(self, terminalreporter, *, rewrite=False):
        self.tr = terminalreporter
        # copy the original stdout for use with CaptureFixture
        self.tr.writer._file = safe_text_dupfile(self.tr.writer._file, mode=self.tr.writer._file.mode)
        self.rewrite = rewrite
        self.__reset()
        steps.subscribe(self.notify)

    def __reset(self):
        self.cur_step = None
        self.cur_resource = None
        self.elements = []

    def __commit(self):
        if self.cur_step and self.rewrite:
            self.tr.writer.write('\n')
            self.tr.writer._lastlen = 0
        self.__reset()

    def __merge_element(self, key, value):
        if self.elements and self.elements[-1][0] == key:
            self.elements.pop()
        if value is not None:
            self.elements.append((key, value))

    def __format_elements(self):
        return [
            "{}={}".format(under(k), repr(v)) for k, v in self.elements if v is not None
        ]

    def notify(self, event):
        new = not self.rewrite
        if not(self.cur_step is event.step):
            new = True
        if self.cur_resource is not event.resource:
            new = True
            self.cur_resource = event.resource
        if new:
            self.__commit()
            self.cur_step = event.step
            self.cur_resource = event.resource
            self.elements = []

        for k, v in event.data.items():
            self.__merge_element(k, v)

        indent = '  '*event.step.level
        line = [indent, bold(event.step.title)]
        if event.resource:
            line.append(event.resource)
        line.extend(self.__format_elements())
        if self.rewrite:
            self.tr.writer.reline(" ".join(line))
        else:
            self.tr.writer.line(" ".join(line))

    @pytest.hookimpl(hookwrapper=True, trylast=True)
    def pytest_runtest_logstart(self):
        outcome = yield
        self.tr.writer.write('\n')
        self.tr.writer._lastlen = 0

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        if report.when == "setup":
            self.__reset()
        elif report.when == "call":
            self.__commit()
        else:
            pass
