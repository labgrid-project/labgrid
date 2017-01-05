import attr


@attr.s
class ExecutionError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class CleanUpError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
