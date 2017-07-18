import attr


@attr.s(cmp=False)
class ExecutionError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s(cmp=False)
class CleanUpError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
