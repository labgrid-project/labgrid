import attr


@attr.s
class NoConfigFoundError(Exception):
    msg = attr.ib()
