import re

from logging import Formatter, StreamHandler, getLogger, BASIC_FORMAT

from .step import steps


def basicConfig(**kwargs):
    stream = kwargs.pop("stream", None)
    handler = StreamHandler(stream)
    root = getLogger()

    dfs = kwargs.pop("datefmt", None)
    fs = kwargs.pop("format", BASIC_FORMAT)
    style = kwargs.pop("style", '%')
    if len(root.handlers) == 0:
        formatter = StepFormatter(fs, dfs, style)
        handler.setFormatter(formatter)
        root.addHandler(handler)



# Use composition instead of inheritance
class StepFormatter:

    def __init__(self, *args, color=None, indent=True, long_result=False):
        self.formatter = Formatter(*args)
        self.color = color
        self.long_result = long_result
        self.indent = indent
        self.indent_level = 0
        self.bufs = dict()
        self.re_vt100 = re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        )

    def format(self, record):
        if hasattr(record, "stepevent"):
            return self.format_step(record)
        else:
            return self.formatter.format(record)

    def format_serial_buffer(self, step):
        if step.source not in self.bufs.keys():
            self.bufs[step.source] = b''
        self.bufs[step.source] += step.result
        *parts, self.bufs[step.source] = self.bufs[step.source].split(b'\r\n')
        result = []
        for part in parts:
            result.append(self.re_vt100.sub('', part.decode("utf-8", errors="replace")))
        return "␍␤\n".join(result)

    def format_console_step(self, record):
        step = record.stepevent.step
        event = record.stepevent
        indent = "  " * (self.indent_level + 1) if self.indent else ""
        if step.get_title() == 'read':
            dirind = "<"
            message = self.format_serial_buffer(step)
            message = message.replace('\n', f'\n{indent}{step.source} {dirind} ')
        else:
            if event.data.get("state", "stop") == "start":
                return
            dirind = ">"
            message = step.args["data"].decode('utf-8')
            message = f"␍␤\n{indent}{step.source} {dirind} ".join(message.split('\n'))
        return f"{indent}{step.source} {dirind} {message}"

    def format_step(self, record):
        step = record.stepevent.step
        if step.tag == 'console' and step.source:
            return self.format_console_step(record)
        if not step.tag:
            return self._line_format(record.stepevent)

    @staticmethod
    def format_arguments(args):
        if args is None:
            return ""
        if isinstance(args, dict):
            collected_args = []
            for k, v in args.items():
                collected_args.append("{}={}".format(k, v))

            return "".join(collected_args)
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

        if len(str(result)) < 20:
            return "result={} ".format(result)
        else:
            return "result={:.19}… ".format(repr(result))

    def _line_format(self, event):
        indent = "  "*event.step.level if self.indent else ""
        self.indent_level = event.step.level

        prefix = "→" if event.data.get("state") == "start" else "←"
        if event.step.exception:
            prefix = "⚠"
        title = '{} {}'.format(prefix, event.step.title)
        line = "{}({}) {}{}".format(title, self.format_arguments(event.data.get('args', {})),
                                    self.format_result(event.data.get('result', None)),
                                    self.format_duration(event.data.get('duration', 0.0)))

        return f"{indent}{line}"


class StepLogger:
    instance = None

    def __init__(self):
        self.logger = getLogger("StepLogger")
        steps.subscribe(self.notify)

    @classmethod
    def start(cls):
        """starts the StepLogger"""
        assert cls.instance is None
        cls.instance = cls()

    @classmethod
    def stop(cls):
        """stops the StepLogger"""
        assert cls.instance is not None
        steps.unsubscribe(cls.notify)
        cls.instance = None

    def notify(self, event):
        self.logger.log(20, event, extra={"stepevent": event})
