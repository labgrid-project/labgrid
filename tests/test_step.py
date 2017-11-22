from time import sleep

from pytest import approx

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
    assert step.duration == approx(0.25, abs=1e-2)

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

def test_method():
    a = A()
    step = a.method_step('foo')
    assert step.title == 'method_step'
    assert step.args is None
    assert step.result is None

def test_method_args():
    a = A()
    step = a.method_args_step('foo')
    assert step.title == 'method_args_step'
    assert step.args == {'foo': 'foo'}
    assert step.result is None

def test_method_title():
    a = A()
    step = a.method_title_step('foo')
    assert step.title == 'test-title'
    assert step.args is None
    assert step.result is None

def test_method_result():
    a = A()
    step = a.method_result_step('foo')
    assert step.title == 'method_result_step'
    assert step.args is None
    assert step.result is step
