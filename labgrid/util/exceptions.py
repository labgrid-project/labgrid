import attr


@attr.s
class NoValidDriverError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
