import attr


@attr.s(cmp=False)
class NoConfigFoundError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s(cmp=False)
class NoSupplierFoundError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s(cmp=False)
class NoDriverFoundError(NoSupplierFoundError):
    pass


@attr.s(cmp=False)
class NoResourceFoundError(NoSupplierFoundError):
    pass
