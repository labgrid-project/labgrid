from .step import steps


class StepReporter:
    instance = None

    @classmethod
    def start(cls):
        assert cls.instance is None
        cls.instance = cls()

    def __init__(self):
        steps.subscribe(self.notify)

    def notify(self, event):
        step = event.step
        indent = '  '*step.level
        print("{}{}".format(indent, event))
