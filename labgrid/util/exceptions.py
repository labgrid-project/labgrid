import attr


@attr.s(cmp=False)
class NoValidDriverError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
