import attr


@attr.s(cmp=False)
class ExecutionError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
    stdout = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(list))
    )
    stderr = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(list))
    )


@attr.s(cmp=False)
class CleanUpError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
