from logging import getLogger

from .step import steps


class StepReporter:
    _started = False

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
