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
            value = f'{value:.3f}'
        if self.elements and self.elements[-1][0] == key:
            self.elements.pop()
        if value is not None:
            self.elements.append((key, value))

    def __format_elements(self):
        return [
            f"{colors.color(k, style='underline')}={repr(v)}" \
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
        title = f'{event.step.source.__class__.__name__}.{event.step.title}'
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
        'expect$': 'blue', # (a lot of output, blend into background)
        'run': 'magenta',
        'state_': 'cyan',
        'transition$': 'yellow',
        'cycle$|on$|off$': 'white',
    }

    EVENT_COLORS_LIGHT = {
        'expect$': 'white', # (a lot of output, blend into background)
        'run': 'magenta',
        'state_': 'cyan',
        'transition$': 'yellow',
        'cycle$|on$|off$': 'blue',
    }

    EVENT_COLORS_DARK_256COLOR = {
        'expect$': 8, # dark gray (a lot of output, blend into background)
        'run': 129, # light purple
        'state_': 51, # light blue
        'transition$': 45, # blue
        'cycle$|on$|off$': 246, # light gray
    }

    EVENT_COLORS_LIGHT_256COLOR = {
        'expect$': 250, # light gray (a lot of output, blend into background)
        'run': 93, # purple
        'state_': 51, # light blue
        'transition$': 45, # blue
        'cycle$|on$|off$': 8, # dark gray
    }

    EVENT_COLOR_SCHEMES = {
        'dark': EVENT_COLORS_DARK,
        'light': EVENT_COLORS_LIGHT,
        'dark-256color': EVENT_COLORS_DARK_256COLOR,
        'light-256color': EVENT_COLORS_LIGHT_256COLOR,
    }

    def __init__(self, terminalreporter, *, rewrite=False):
        super().__init__(terminalreporter, rewrite=rewrite)

        try:
            import curses
            default_scheme = 'dark'
            curses.setupterm()
            if curses.tigetnum("colors") >= 256:
                default_scheme = 'dark-256color'
        except ModuleNotFoundError:
            default_scheme = 'dark-256color'

        scheme = os.environ.get('LG_COLOR_SCHEME', default_scheme)
        if scheme not in ColoredStepReporter.EVENT_COLOR_SCHEMES.keys():
            logging.warning("Color scheme '%s' unknown", scheme)
            scheme = default_scheme

        self.color_scheme = ColoredStepReporter.EVENT_COLOR_SCHEMES[scheme]

    def __event_color(self, event):
        for pattern, color in self.color_scheme.items():
            if re.match(pattern, event.step.title):
                return color

        return 'default'

    def __format_elements(self, color):
        return [
            colors.color(k, fg=color, style='underline') + \
                colors.color(f'={repr(v)}', fg=color) \
                    for k, v in self.elements if v is not None
        ]

    def _line_format(self, event):
        indent = '  '*event.step.level
        color = self.__event_color(event)
        title = f'{event.step.source.__class__.__name__}.{event.step.title}'
        line = [indent, colors.color(title, fg=color, style='bold')]
        if event.resource:
            line.append(event.resource)
        line.extend(self.__format_elements(color))
        if self.rewrite:
            self.tr._tw.reline(" ".join(line))
        else:
            self.tr._tw.line(" ".join(line))
