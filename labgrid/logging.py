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

    def __init__(self, *args, color=None):
        self.formatter = Formatter(*args)
        self.color = color

    def format(self, record):
        if hasattr(record, "step"):
            return self.formt_step(record)
        else:
            return self.formatter.format(record)

    def format_step(self, record):
        return f"  {record.getMessage}"


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
        self.logger.log(15, event)
