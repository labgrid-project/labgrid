import time

import attr


@attr.s(eq=False)
class Timeout:
    """Reperents a timeout (as a deadline)"""
    timeout = attr.ib(
        default=120.0, validator=attr.validators.instance_of(float)
    )

    def __attrs_post_init__(self):
        if self.timeout < 0.0:
            raise ValueError("timeout must be positive")
        self._deadline = time.monotonic() + self.timeout

    @property
    def remaining(self):
        result = self._deadline - time.monotonic()
        return result if result > 0.0 else 0.0

    @property
    def expired(self):
        return self._deadline <= time.monotonic()
