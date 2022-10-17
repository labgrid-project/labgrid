from logging import getLogger

from .step import steps


class StepReporter:
    _started = False

    def __init__(self):
        from warnings import warn

        warn(
            "StepReporter should not be instantiated, use StepReporter.start()/.stop() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    @classmethod
    def start(cls):
        """starts the StepReporter"""
        assert not cls._started
        steps.subscribe(cls.notify)
        cls._started = True

    @classmethod
    def stop(cls):
        """stops the StepReporter"""
        assert cls._started
        steps.unsubscribe(cls.notify)
        cls._started = False

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
