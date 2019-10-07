import attr


@attr.s(eq=False)
class NoValidDriverError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
