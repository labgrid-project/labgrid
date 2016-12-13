import attr


@attr.s
class NoDriverError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class NoResourceError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
