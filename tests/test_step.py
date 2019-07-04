from time import sleep

import pytest

from labgrid import step, steps


@step()
def step_a(*, step):
    assert steps.get_current() is not None
    return step.level

@step()
def step_outer(*, step):
    assert step.level == 1
    return step_a()

def test_single():
    assert steps.get_current() is None
    step_a()
    assert steps.get_current() is None

def test_nested():
    assert steps.get_current() is None
    inner_level = step_outer()
    assert steps.get_current() is None
    assert inner_level == 2

@step()
def step_sleep(*, step):
    sleep(0.25)
    return step

def test_timing():
    step = step_sleep()
    assert step.duration == pytest.approx(0.25, abs=1e-2)
    assert step.exception is None

class A:
    @step()
    def method_step(self, foo, *, step):
        return step

    @step(args=['foo'])
    def method_args_step(self, foo, *, step):
        return step

    @step(title='test-title')
    def method_title_step(self, foo, *, step):
        return step

    @step(result=True)
    def method_result_step(self, foo, *, step):
        return step

    @step(tag='dummy')
    def method_tag_step(self, foo, *, step):
        return step

def test_method():
    a = A()
    step = a.method_step('foo')
    assert step.source == a
    assert step.title == 'method_step'
    assert step.args is None
    assert step.result is None
    assert step.tag is None

def test_method_args():
    a = A()
    step = a.method_args_step('foo')
    assert step.source == a
    assert step.title == 'method_args_step'
    assert step.args == {'foo': 'foo'}
    assert step.result is None
    assert step.tag is None

def test_method_title():
    a = A()
    step = a.method_title_step('foo')
    assert step.source == a
    assert step.title == 'test-title'
    assert step.args is None
    assert step.result is None
    assert step.tag is None

def test_method_result():
    a = A()
    step = a.method_result_step('foo')
    assert step.source == a
    assert step.title == 'method_result_step'
    assert step.args is None
    assert step.result is step
    assert step.tag is None

def test_method_tag():
    a = A()
    step = a.method_tag_step('foo')
    assert step.source == a
    assert step.title == 'method_tag_step'
    assert step.args is None
    assert step.result is None
    assert step.tag == 'dummy'

@step(args=['default'])
def step_default_arg(default=None, *, step):
    return step

def test_default_arg():
    step = step_default_arg()
    assert step.args['default'] == None

    step = step_default_arg(default='real')
    assert step.args['default'] == 'real'

@step()
def step_error(output, *, step):
    output.append(step)
    raise ValueError('dummy')

def test_error():
    output = []
    with pytest.raises(ValueError, match=r'dummy'):
        step_error(output)
    step = output[0]
    assert step.exception is not None
    assert isinstance(step.exception, ValueError)

@step()
def step_event_skip(*, step):
    step.skip('testing')

def test_event():
    events = []
    def callback(event):
        events.append(event)

    steps.subscribe(callback)
    try:
        step = step_event_skip()
    finally:
        steps.unsubscribe(callback)

    skip_event = [e for e in events if 'skip' in e.data]
    assert len(skip_event) == 1
    assert skip_event[0].data['skip'] == 'testing'

def test_subscriber_error():
    events = []
    def callback(event):
        raise ValueError('from callback')

    steps.subscribe(callback)
    with pytest.warns(UserWarning):
        step = step_event_skip()
    steps.unsubscribe(callback)
