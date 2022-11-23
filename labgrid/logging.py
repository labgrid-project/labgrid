import re

import logging

from .step import steps


def basicConfig(**kwargs):
    logging.basicConfig(**kwargs)
    root = logging.getLogger()

    root.handlers[0].setFormatter(StepFormatter())

# Use composition instead of inheritance
class StepFormatter:

    def __init__(self, *args, color=None, indent=True, long_result=False, **kwargs):
        self.formatter = logging.Formatter(**kwargs)
        self.color = color
        self.long_result = long_result
        self.indent = indent
        self.indent_level = 0
        self.bufs = dict()
        self.re_vt100 = re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        )

    def format(self, record):
        if getattr(record, "console", False):
            return self.format_console_step(record)
        # TODO: Add flushing of previously received console bytes
        if hasattr(record, "stepevent"):
            return self._line_format(record.stepevent)
        else:
            return self.formatter.format(record)

    def format_serial_buffer(self, step):
        if step.source not in self.bufs.keys():
            self.bufs[step.source] = b''
        assert step.result is not None
        self.bufs[step.source] += step.result
        *parts, self.bufs[step.source] = self.bufs[step.source].split(b'\r\n')
        result = []
        for part in parts:
            result.append(self.re_vt100.sub('', part.decode("utf-8", errors="replace")))
        return "␍␤\n".join(result)

    def format_console_step(self, record):
        step = record.stepevent.step
        indent = "  " * (self.indent_level + 1) if self.indent else ""
        if step.get_title() == 'read':
            dirind = "<"
            message = self.format_serial_buffer(step)
            message = message.replace('\n', f'\n{indent}{step.source} {dirind} ')
        else:
            dirind = ">"
            message = step.args["data"].decode('utf-8')
            message = f"␍␤\n{indent}{step.source} {dirind} ".join(message.split('\n'))
        return f"{indent}{step.source} {dirind} {message}"

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
            return "!"
        elif event.data.get("state") == "start":
            return "→"
        elif event.data.get("state") == "stop":
            return "←"
        elif event.data.get("skip", None):
            return "S"
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

class StepLogger:
    _started = False
    _logger = None

    def __init__(self):
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
        cls._started = True

    @classmethod
    def stop(cls):
        """stops the StepLogger"""
        assert cls._started
        steps.unsubscribe(cls.notify)
        cls._started = False

    @classmethod
    def notify(cls, event):
        level = logging.INFO
        step = event.step
        extra = {"stepevent": event}
        if step.tag == "console":
            if event.data.get("state", None) == "start" and step.get_title() == "write":
                level = logging.DEBUG
            elif step.get_title() == "read" and not step.result:
                level = logging.DEBUG
            else:
                extra["console"] = True

        cls._logger.log(level, event, extra=extra)
