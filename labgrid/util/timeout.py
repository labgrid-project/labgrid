import attr


@attr.s
class PtxTimeout(object):
    """Saves a class specific Timeout"""
    cls = attr.ib()
    timeout = attr.ib(default=120, validator=attr.validators.instance_of(int))
