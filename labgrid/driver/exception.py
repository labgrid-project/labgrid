import attr


@attr.s
class NoDriveError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class NoResourcError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
