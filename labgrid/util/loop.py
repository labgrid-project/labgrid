import asyncio
from contextvars import ContextVar


_loop: ContextVar["asyncio.AbstractEventLoop | None"] = ContextVar("_loop", default=None)
_last_created_loop: ContextVar["asyncio.AbstractEventLoop | None"] = ContextVar("_last_created_loop:", default=None)

def ensure_event_loop(external_loop=None):
    """Get the event loop for this thread, or create a new event loop."""
    # get stashed loop
    loop = _loop.get()

    # ignore closed stashed loop
    if loop and loop.is_closed():
        loop = None

    if external_loop:
        # if a loop is stashed, expect it to be the same as the external one
        if loop:
            assert loop is external_loop
        _loop.set(external_loop)
        return external_loop

    # return stashed loop
    if loop:
        return loop

    try:
        # if called from async code, try to get current's thread loop
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # no previous, external or running loop found, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # stash new loop
        _last_created_loop.set(loop)

    # stash loop
    _loop.set(loop)
    return loop

def is_new_loop(loop):
    """Check whether the given loop was created in ensure_event_loop() before."""
    return loop is _last_created_loop.get()
