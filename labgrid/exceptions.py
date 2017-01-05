import attr


@attr.s
class NoConfigFoundError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class NoDriverFoundError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class NoResourceFoundError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
