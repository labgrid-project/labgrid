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
        from warnings import warn
        warn(
            """
            StepReporter is deprecated, use the StepLogger and basicConfig from labgrid.logging
            instead which integrates with the python logging infrastructure.
            """,
            DeprecationWarning,
            stacklevel=2,
        )
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
