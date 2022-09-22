import attr


@attr.s(eq=False)
class NoConfigFoundError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s(eq=False)
class NoSupplierFoundError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
    filter = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(set))
    )


@attr.s(eq=False)
class InvalidConfigError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s(eq=False)
class NoDriverFoundError(NoSupplierFoundError):
    pass


@attr.s(eq=False)
class NoResourceFoundError(NoSupplierFoundError):
    found = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(list))
    )


@attr.s(eq=False)
class NoStrategyFoundError(NoSupplierFoundError):
    pass


@attr.s(eq=False)
class RegistrationError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
