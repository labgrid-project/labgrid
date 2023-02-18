import re

import logging
import os
import colors

import attr

from .step import steps, StepEvent

def basicConfig(**kwargs):
    logging.basicConfig(**kwargs)
    root = logging.getLogger()

    root.handlers[0].setFormatter(StepFormatter())

# Use composition instead of inheritance
class StepFormatter:
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

    def __init__(self, *args, indent=True, long_result=False, color=False, **kwargs):
        self.formatter = logging.Formatter(**kwargs)
        self.long_result = long_result
        self.indent = indent
        self.indent_level = 0
        self.bufs = dict()
        self.re_vt100 = re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        )
        self.color = color
        if color:
            try:
                import curses
                default_scheme = 'dark'
                curses.setupterm()
                if curses.tigetnum("colors") >= 256:
                    default_scheme = 'dark-256color'
            except ModuleNotFoundError:
                default_scheme = 'dark-256color'

            scheme = os.environ.get('LG_COLOR_SCHEME', default_scheme)
            if scheme not in StepFormatter.EVENT_COLOR_SCHEMES.keys():
                logging.warning("Color scheme '%s' unknown", scheme)
                scheme = default_scheme
            self.color_scheme = StepFormatter.EVENT_COLOR_SCHEMES[scheme]
        else:
            self.color_scheme = None

    def __event_color(self, event):
        for pattern, color in self.color_scheme.items():
            if re.match(pattern, event.step.title):
                return color

        return 'default'

    def format(self, record):
        if hasattr(record, "consoleevent"):
            return self.format_console_step(record)
        # TODO: Add flushing of previously received console bytes
        if hasattr(record, "stepevent"):
            return self._line_format(record.stepevent)
        else:
            return self.formatter.format(record)

    def format_console_step(self, record):
        step = record.consoleevent.step
        indent = "  " * (self.indent_level + 1) if self.indent else ""
        color = 'default'
        if self.color:
            color = 250
        if step.get_title() == 'read':
            dirind = "<"
        else:
            dirind = ">"
        if self.color:
            return f"{indent}{colors.color(step.source, fg=color, style='bold')} {colors.color(dirind, fg=color)} {record.msg}"
        else:
            return f"{indent}{step.source} {dirind} {record.msg}"

    @staticmethod
    def format_arguments(args):
        if args is None:
            return ""
        if isinstance(args, dict):
            collected_args = []
            for k, v in args.items():
                collected_args.append("{}={}".format(k, v))

            return " ".join(collected_args)
        else:
            return "{}".format(args)

    @staticmethod
    def format_duration(duration):
        if duration < 0.001:
            return ""

        return "[{:.3f}s]".format(duration)

    def format_result(self, result):
        if result is None:
            return ""

        if self.long_result:
            return "result={} ".format(result)

        if len(str(result)) < 60:
            return "result={} ".format(result)
        else:
            return "result={:.59}… ".format(repr(result))

    def get_prefix(self, event):
        if event.step.exception:
            return "⚠"
        elif event.data.get("state") == "start":
            return "→"
        elif event.data.get("state") == "stop":
            return "←"
        elif event.data.get("skip", None):
            return "↓"
        else:
            return ""

    def _line_format(self, event):
        indent = "  " * event.step.level if self.indent else ""
        self.indent_level = event.step.level

        prefix = self.get_prefix(event)

        title = '{} {}.{}'.format(prefix, event.step.source.__class__.__name__, event.step.title)
        line = "{} {} {}{}".format(title, self.format_arguments(event.data.get('args', {})),
                                    self.format_result(event.data.get('result', None)),
                                    self.format_duration(event.data.get('duration', 0.0)))

        if event.step.exception:
            line = f"{line} exception={event.step.exception}"

        reason = event.data.get("skip", None)
        if reason:
            line = f"{line}skipped={reason}"

        return f"{indent}{line}"

@attr.s
class SerialLoggingReporter():
    bufs = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))
    loggers = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))
    lastevent = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(StepEvent)))
    re_vt100 = attr.ib(
        default=re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        ))

    def __attrs_post_init__(self):
        steps.subscribe(self.notify)

    def notify(self, event):
        step = event.step
        if step.tag == 'console' and step.get_title() == 'read' \
           and event.data.get('state') == 'stop' and step.result:
            self.loggers[step.source] = logging.getLogger(f"SerialLogger.{step.source.__class__.__name__}.{step.source.target}")
            logger = self.loggers[step.source]
            if step.source not in self.bufs.keys():
                self.bufs[step.source] = b''
            self.bufs[step.source] += step.result
            *parts, self.bufs[step.source] = self.bufs[step.source].split(b'\r\n')

            extra = {"consoleevent": event}
            self.lastevent = event

            for part in parts:
                data = self.re_vt100.sub('', part.decode("utf-8", errors="replace"))
                logger.info("{}␍␤".format(data), extra=extra)

    def flush(self):
        if self.lastevent is None:
            return

        extra = {"consoleevent": self.lastevent}
        for source, logger in self.loggers.items():
            data = self.re_vt100.sub('', self.bufs[source].decode("utf-8", errors="replace"))
            if data:
                logger.info(data, extra=extra)
            self.bufs[source] = b""


class StepLogger:
    _started = False
    _logger = None
    _serial_logger = None

    def __attrs_post_init__(self):
        from warnings import warn

        warn(
            "StepLogger should not be instantiated, use StepReporter.start()/.stop() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    @classmethod
    def start(cls):
        """starts the StepLogger"""
        assert not cls._started
        if cls._logger is None:
            cls._logger = logging.getLogger("StepLogger")
        steps.subscribe(cls.notify)
        cls._serial_logger = SerialLoggingReporter()
        cls._started = True

    @classmethod
    def stop(cls):
        """stops the StepLogger"""
        assert cls._started
        steps.unsubscribe(cls.notify)
        cls._started = False

    @classmethod
    def notify(cls, event):
        if event.step.tag == "console":
            return
        if cls._serial_logger:
            cls._serial_logger.flush()

        level = logging.INFO
        step = event.step
        extra = {"stepevent": event}
        cls._logger.log(level, event, extra=extra)
