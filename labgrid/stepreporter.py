import logging
import pprint
import re

import attr

from .step import steps
from .protocol import ConsoleProtocol


class StepReporter:
    instance = None

    @classmethod
    def start(cls):
        """starts the StepReporter"""
        assert cls.instance is None
        cls.instance = cls()

    @classmethod
    def stop(cls):
        """stops the StepReporter"""
        assert cls.instance is not None
        steps.unsubscribe(cls.notify)
        cls.instance = None

    def __init__(self):
        steps.subscribe(StepReporter.notify)

    @staticmethod
    def notify(event):
        # ignore tagged events
        if event.step.tag:
            return

        step = event.step
        indent = '  '*step.level
        print("{}{}".format(indent, event))


@attr.s
class StepGetLoggerMixin:
    @staticmethod
    def get_logger(step):
        if step.source.name:
            return logging.getLogger("{}.{}.{}".format(
                step.source.target.name, step.source.__class__.__name__, step.source.name
            ))
        else:
            return logging.getLogger("{}.{}".format(
                step.source.target.name, step.source.__class__.__name__
            ))


@attr.s
class SerialLoggingReporter(StepGetLoggerMixin):
    bufs = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))
    loggers = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))
    re_vt100 = attr.ib(
        default=re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        ))

    def __attrs_post_init__(self):
        steps.subscribe(self.notify)

    def notify(self, event):
        step = event.step
        if step.tag == 'console' and str(step) == 'read' \
           and event.data.get('state') == 'stop' and step.result:
            self.loggers[step.source] = self.get_logger(step)
            logger = self.loggers[step.source]
            if step.source not in self.bufs.keys():
                self.bufs[step.source] = b''
            self.bufs[step.source] += step.result
            *parts, self.bufs[step.source] = self.bufs[step.source].split(b'\r\n')
            for part in parts:
                data = self.re_vt100.sub('', part.decode("utf-8", errors="replace"))
                logger.info("{}␍␤".format(data))

    def flush(self):
        for source, logger in self.loggers.items():
            data = self.re_vt100.sub('', self.bufs[source].decode("utf-8", errors="replace"))
            if data:
                logger.info(data)
            self.bufs[source] = b""


@attr.s
class StepLoggingReporter(StepGetLoggerMixin):
    indent = attr.ib(default=False, validator=attr.validators.instance_of(bool))
    long_result = attr.ib(default=False, validator=attr.validators.instance_of(bool))
    serial_reporter = attr.ib(default=None,
                              validator=attr.validators.optional(
                                  attr.validators.instance_of(SerialLoggingReporter)))

    def __attrs_post_init__(self):
        steps.subscribe(self.notify)

    def notify(self, event):
        # ignore tagged events
        if event.step.tag:
            return
        if self.serial_reporter:
            self.serial_reporter.flush()

        self._line_format(event)

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
        step = event.step

        logger = self.get_logger(step)
        prefix = "→" if event.data.get("state") == "start" else "←"
        if event.step.exception:
            prefix = "⚠"
        title = '{} {}'.format(prefix, event.step.title)
        line = ["{}({}) {}{}".format(title,
                                     self.format_arguments(event.data.get('args', {})),
                                     self.format_result(event.data.get('result', None)),
                                     self.format_duration(event.data.get('duration', 0.0)))
                ]
        logger.info("%s%s", indent, line[0])
