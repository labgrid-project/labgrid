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
