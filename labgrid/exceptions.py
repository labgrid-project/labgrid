import attr


@attr.s
class NoConfigFoundError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class NoSupplierFoundError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class NoDriverFoundError(NoSupplierFoundError):
    pass


@attr.s
class NoResourceFoundError(NoSupplierFoundError):
    pass
