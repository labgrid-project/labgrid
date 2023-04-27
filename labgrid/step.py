import inspect
import os
import warnings
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

    def get_new(self, title, tag, source, sourceinfo):
        step = Step(title, level=len(self._stack) + 1, tag=tag, source=source, sourceinfo=sourceinfo)  # pylint: disable=redefined-outer-name
        return step

    def push(self, step):  # pylint: disable=redefined-outer-name
        assert step not in self._stack
        self._stack.append(step)
        step.parent = self.get_current()
        step.level = len(self._stack)

    def pop(self, step):  # pylint: disable=redefined-outer-name
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
            except Exception as e:  # pylint: disable=broad-except
                warnings.warn(f"unhandled exception during event notification: {e}")

steps = Steps()


class StepEvent:
    def __init__(self, step, data, *, resource=None, stream=False):  # pylint: disable=redefined-outer-name
        self.ts = monotonic()  # used to keep track of the events age
        self.step = step
        self.data = data
        self.resource = resource
        self.stream = stream

    def __str__(self):
        result = [self.step.title]
        if self.resource:
            result.append(self.resource.__class__.__name__)
        data = self.data.copy()
        duration = data.pop('duration', 0.0)
        pairs = [f"{k}={repr(v)}" for k, v in data.items() if v is not None]
        if duration >= 0.001:
            pairs.append(f"duration={duration:.3f}")
        result.append(", ".join(pairs))
        return " ".join(result)

    def __setitem__(self, k, v):
        self.data[k] = v

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
    def __init__(self, title, level, tag, source, sourceinfo):
        self.title = title
        self.level = level
        self.tag = tag
        self.source = source
        self.sourceinfo = sourceinfo
        self.args = None
        self.result = None
        self.exception = None
        self._start_ts = None
        self._stop_ts = None
        self._skipped = False

    def __repr__(self):
        result = [
            f"Step(title={self.title!r}, level={self.level}, status={self.status}"
        ]
        if self.args is not None:
            result.append(f", args={self.args}")
        if self.exception is not None:
            result.append(f", exception={self.exception}")
        if self.result is not None:
            result.append(f", result={self.result}")
        duration = self.duration
        if duration >= 0.001:
            result.append(f", duration={duration:.3f}")
        result.append(")")
        return "".join(result)

    @property
    def duration(self):
        if self._start_ts is None:
            return 0.0
        if self._stop_ts is None:
            return monotonic() - self._start_ts

        return self._stop_ts - self._start_ts

    @property
    def status(self):
        if self._start_ts is None:
            return 'new'
        if self._stop_ts is None:
            return 'active'

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
        event = StepEvent(self, {'state': 'stop'})
        if self.exception:
            event['exception'] = self.exception
        else:
            event['result'] = self.result
        duration = self.duration
        if duration:
            event['duration'] = duration
        self._notify(event)
        steps.pop(self)

    def __del__(self):
        if not self.is_done:
            warnings.warn(f"__del__ called before {step} was done")


def step(*, title=None, args=[], result=False, tag=None):
    def decorator(func):
        # resolve default title
        nonlocal title
        title = title or func.__name__

        signature = inspect.signature(func)
        @wraps(func)
        def wrapper(*_args, **_kwargs):
            bound = signature.bind_partial(*_args, **_kwargs)
            bound.apply_defaults()
            source = func.__self__ if inspect.ismethod(func) else bound.arguments.get('self')
            pathname = func.__code__.co_filename
            sourceinfo = (pathname,  os.path.basename(pathname), func.__code__.co_firstlineno)
            step = steps.get_new(title, tag, source, sourceinfo)  # pylint: disable=redefined-outer-name
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
            except Exception as e:
                step.exception = e
                raise
            finally:
                step.stop()
            return _result

        return wrapper

    return decorator
