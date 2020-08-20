import logging
import sys
import os
import re
import colors
import pytest

from ..step import steps

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)


def safe_dupfile(f):
    if pytest.__version__ < "6.0.0":
        from _pytest.capture import safe_text_dupfile
        return safe_text_dupfile(f, mode=f.mode)
    else:
        from _pytest.capture import EncodedFile
        default_encoding = "UTF8"

        encoding = getattr(f, "encoding", None)
        try:
            fd = f.fileno()
        except OSError:
            if "b" not in getattr(f, "mode", "") and hasattr(f, "encoding"):
                # we seem to have a text stream, let's just use it
                return f

        newfd = os.dup(fd)
        mode = f.mode
        if "b" not in mode:
            mode += "b"
        f = os.fdopen(newfd, mode, 0)  # no buffering

        return EncodedFile(f, encoding or default_encoding, errors="replace",
                           write_through=True)


class StepReporter:
    def __init__(self, terminalreporter, *, rewrite=False):
        self.tr = terminalreporter
        # copy the original stdout for use with CaptureFixture
        self.tr._tw._file = safe_dupfile(self.tr._tw._file)
        self.rewrite = rewrite and pytest.__version__ < "6.0.0"
        self.__reset()
        steps.subscribe(self.notify)

    def __reset(self):
        self.cur_step = None
        self.cur_resource = None
        self.elements = []

    def __commit(self):
        if self.cur_step and self.rewrite:
            self.tr._tw.write('\n')
            self.tr._tw._lastlen = 0
        self.__reset()

    def __merge_element(self, key, value):
        if key == 'duration':
            if value < 0.001:
                return
            value = '{:.3f}'.format(value)
        if self.elements and self.elements[-1][0] == key:
            self.elements.pop()
        if value is not None:
            self.elements.append((key, value))

    def __format_elements(self):
        return [
            "{}={}".format(colors.color(k, style='underline'), repr(v)) \
                for k, v in self.elements if v is not None
        ]

    def notify(self, event):
        # ignore tagged events
        if event.step.tag:
            return

        new = not self.rewrite
        if self.cur_step is not event.step:
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

        self._line_format(event)

    def _line_format(self, event):
        indent = '  '*event.step.level
        title = '{}.{}'.format(event.step.source.__class__.__name__, event.step.title)
        line = [indent, colors.color(title, style='bold')]
        if event.resource:
            line.append(event.resource)
        line.extend(self.__format_elements())
        if self.rewrite:
            self.tr._tw.reline(" ".join(line))
        else:
            self.tr._tw.line(" ".join(line))

    @pytest.hookimpl(hookwrapper=True, trylast=True)
    def pytest_runtest_logstart(self):
        yield
        self.tr._tw.write('\n')
        self.tr._tw._lastlen = 0

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        if report.when == "setup":
            self.__reset()
        elif report.when == "call":
            self.__commit()
        else:
            pass


class ColoredStepReporter(StepReporter):
    EVENT_COLORS_DARK = {
        'expect$': 8, # dark gray (a lot of output, blend into background)
        'run': 10, # green
        'state_': 51, # light blue
        'transition$': 45, # blue
        'cycle$|on$|off$': 246, # light gray
    }

    EVENT_COLORS_LIGHT = {
        'expect$': 250, # light gray (a lot of output, blend into background)
        'run': 10, # green
        'state_': 51, # light blue
        'transition$': 45, # blue
        'cycle$|on$|off$': 8, # dark gray
    }

    def __init__(self, terminalreporter, *, rewrite=False):
        super().__init__(terminalreporter, rewrite=rewrite)

        scheme = os.environ.get('LG_COLOR_SCHEME', 'dark')
        if scheme == 'light':
            self.color_scheme = ColoredStepReporter.EVENT_COLORS_LIGHT
        else:
            self.color_scheme = ColoredStepReporter.EVENT_COLORS_DARK

    def __event_color(self, event):
        for pattern, color in self.color_scheme.items():
            if re.match(pattern, event.step.title):
                return color

        return 'default'

    def __format_elements(self, color):
        return [
            colors.color(k, fg=color, style='underline') + \
                colors.color('={}'.format(repr(v)), fg=color) \
                    for k, v in self.elements if v is not None
        ]

    def _line_format(self, event):
        indent = '  '*event.step.level
        color = self.__event_color(event)
        title = '{}.{}'.format(event.step.source.__class__.__name__, event.step.title)
        line = [indent, colors.color(title, fg=color, style='bold')]
        if event.resource:
            line.append(event.resource)
        line.extend(self.__format_elements(color))
        if self.rewrite:
            self.tr._tw.reline(" ".join(line))
        else:
            self.tr._tw.line(" ".join(line))
