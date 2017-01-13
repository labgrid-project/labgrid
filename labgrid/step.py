import warnings
from functools import wraps
from time import monotonic


# TODO: collect events from all Steps and combine when possible, only flush
# after some time
class Steps:
    def __init__(self):
        self._stack = []

    def get_current(self):
        return self._stack[-1] if self._stack else None

    def get_new(self, title):
        step = Step(title, level=len(self._stack) + 1)
        return step

    def push(self, step):
        assert step not in self._stack
        self._stack.append(step)
        step.parent = self.get_current()
        step.level = len(self._stack)

    def pop(self, step):
        assert self._stack[-1] is step
        self._stack.pop()


steps = Steps()


# TODO: allow attaching log information, using a Resource as meta-data
class Step:
    def __init__(self, title, level):
        self.title = title
        self.level = level
        self.args = repr(())
        self.kwargs = repr({})
        self._start_ts = None
        self._stop_ts = None

    def __repr__(self):
        result = [
            "Step(title={!r}, level={}, status={}".format(
                self.title,
                self.level,
                self.status,
            )
        ]
        if self.args != repr(()):
            result.append(", args={}".format(self.args))
        if self.kwargs != repr({}):
            result.append(", kwargs={}".format(self.kwargs))
        duration = self.duration
        if duration >= 0.001:
            result.append(", duration={:.3f}".format(duration))
        result.append(")")
        return ''.join(result)

    @property
    def duration(self):
        if self._start_ts is None:
            return 0.0
        elif self._stop_ts is None:
            return monotonic() - self._start_ts
        else:
            return self._stop_ts - self._start_ts

    @property
    def status(self):
        if self._start_ts is None:
            return 'new'
        elif self._stop_ts is None:
            return 'active'
        else:
            return 'done'

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def is_done(self):
        return self.status == 'done'

    def start(self):
        assert self._start_ts is None
        self._start_ts = monotonic()
        print("start {}".format(self))
        steps.push(self)

    def stop(self):
        assert self._start_ts is not None
        assert self._stop_ts is None
        steps.pop(self)
        self._stop_ts = monotonic()
        print("stop {}".format(self))

    def __del__(self):
        if not self.is_done:
            warnings.warn("__del__ called before {} was done".format(step))


def step(title):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            step = steps.get_new(title)
            step.args = repr(args[1:])
            step.kwargs = repr(kwargs)
            step.start()
            try:
                result = func(*args, step=step, **kwargs)
            finally:
                step.stop()
            return result

        return wrapper

    return decorator
