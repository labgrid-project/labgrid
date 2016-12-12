import attr


@attr.s
class NoDriverException(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class NoResourceException(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
