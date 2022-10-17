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



class StepFormatter(Formatter):

    def __init__(self, *args):
        super().__init__(*args)

    def format(self, record):
        if hasattr(record, "step"):
            return self.formt_step(record)
        else:
            return self.format_normal(record)

    def format_normal(self, record):
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        s = self.formatMessage(record)
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + record.exc_text
        if record.stack_info:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + self.formatStack(record.stack_info)
        return s


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
