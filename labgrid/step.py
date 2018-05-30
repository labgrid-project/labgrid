import warnings
import inspect
from functools import wraps
from time import monotonic


# TODO: collect events from all Steps and combine when possible, only flush
# after some time
class Steps:
    def __init__(self):
        self._stack = []
        self._subscribers = []

    def get_current(self):
        return self._stack[-1] if self._stack else None

    def get_new(self, title, tag, source):
        step = Step(title, level=len(self._stack) + 1, tag=tag, source=source)
        return step

    def push(self, step):
        assert step not in self._stack
        self._stack.append(step)
        step.parent = self.get_current()
        step.level = len(self._stack)

    def pop(self, step):
        assert self._stack[-1] is step
        self._stack.pop()

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def unsubscribe(self, callback):
        assert callback in self._subscribers
        self._subscribers.remove(callback)

    def notify(self, event):
        # TODO: buffer and try to merge consecutive events
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception as e:
                warnings.warn("unhandled exception during event notification: {}".format(e))

steps = Steps()


class StepEvent:
    def __init__(self, step, data, *, resource=None, stream=False):
        self.ts = monotonic()  # used to keep track of the events age
        self.step = step
        self.data = data
        self.resource = resource
        self.stream = stream

    def __str__(self):
        result = [str(self.step)]
        if self.resource:
            result.append(self.resource.__class__.__name__)
        result.append(", ".join(
            "{}={}".format(k, repr(v)) for k, v in self.data.items() if v is not None
        ))
        return " ".join(result)

    def _invalidate(self):
        self.ts = None
        self.step = None
        self.data = None
        self.resource = None
        self.stream = None

    def merge(self, other):
        if not self.stream and not other.stream:
            return False
        if self.ts > other.ts:
            return False
        if self.resource is not other.resource:
            return False
        if self.data.keys() != other.data.keys():
            return False
        for k, v in other.data:
            self.data[k] += v
        other._invalidate()
        return True

    @property
    def age(self):
        return monotonic() - self.ts


# TODO: allow attaching log information, using a Resource as meta-data
class Step:
    def __init__(self, title, level, tag, source):
        self.title = title
        self.level = level
        self.source = source
        self.tag = tag
        self.args = None
        self.result = None
        self._start_ts = None
        self._stop_ts = None
        self._skipped = False

    def __repr__(self):
        result = [
            "Step(title={!r}, level={}, status={}".format(
                self.title,
                self.level,
                self.status,
            )
        ]
        if self.args is not None:
            result.append(", args={}".format(self.args))
        if self.result is not None:
            result.append(", result={}".format(self.result))
        duration = self.duration
        if duration >= 0.001:
            result.append(", duration={:.3f}".format(duration))
        result.append(")")
        return "".join(result)

    def __str__(self):
        return "{}".format(self.title)

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

    def _notify(self, event: StepEvent):
        assert event.step is self
        steps.notify(event)

    def start(self):
        assert self._start_ts is None
        self._start_ts = monotonic()
        steps.push(self)
        self._notify(StepEvent(self, {
            'state': 'start',
            'args': self.args,
        }))

    def skip(self, reason):
        assert self._start_ts is not None
        self._notify(StepEvent(self, {'skip': reason}))

    def stop(self):
        assert self._start_ts is not None
        assert self._stop_ts is None
        self._stop_ts = monotonic()
        # TODO: report duration
        self._notify(StepEvent(self, {
            'state': 'stop',
            'result': self.result,
        }))
        steps.pop(self)

    def __del__(self):
        if not self.is_done:
            warnings.warn("__del__ called before {} was done".format(step))


def step(*, title=None, args=[], result=False, tag=None):
    def decorator(func):
        # resolve default title
        nonlocal title
        title = title or func.__name__

        signature = inspect.signature(func)

        @wraps(func)
        def wrapper(*_args, **_kwargs):
            bound = signature.bind_partial(*_args, **_kwargs)
            # TODO: replace this by bound.apply_defaults() when deprecating
            # python3.4 support
            for name, param in signature.parameters.items():
                bound.arguments.setdefault(name, param.default)
            source = bound.arguments.get('self')
            step = steps.get_new(title, tag, source)
            # optionally pass the step object
            if 'step' in signature.parameters:
                _kwargs['step'] = step
            if args:
                step.args = {k: bound.arguments[k] for k in args}
            step.start()
            try:
                _result = func(*_args, **_kwargs)
                if result:
                    step.result = _result
            finally:
                step.stop()
            return _result

        return wrapper

    return decorator
