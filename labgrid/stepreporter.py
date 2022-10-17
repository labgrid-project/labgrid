from logging import getLogger

from .step import steps


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
        print(f"{indent}{event}")


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
