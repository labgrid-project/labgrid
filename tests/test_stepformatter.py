import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from labgrid.logging import StepFormatter


def make_record(message, **extra):
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    record.__dict__.update(extra)
    return record


def test_stepformatter_construction():
    formatter = StepFormatter("%(message)s")

    assert formatter.format(make_record("message")) == "message"


def test_stepformatter_indent_is_thread_local():
    formatter = StepFormatter("%(message)s")
    first_formatted = Event()
    release_first = Event()

    def first_thread():
        step_message = formatter.format(
            make_record("step", indent_level=1, next_indent_level=2)
        )
        first_formatted.set()
        assert release_first.wait(timeout=2)
        nested_message = formatter.format(make_record("nested"))
        return step_message, nested_message

    def second_thread():
        assert first_formatted.wait(timeout=2)
        try:
            return formatter.format(make_record("other"))
        finally:
            release_first.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(first_thread)
        second = executor.submit(second_thread)
        assert first.result(timeout=2) == (" step", "  nested")
        assert second.result(timeout=2) == "other"
