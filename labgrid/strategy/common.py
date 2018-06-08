import attr

from ..binding import BindingError
from ..driver import Driver


@attr.s(cmp=False)
class StrategyError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


@attr.s(cmp=False)
class Strategy(Driver):  # reuse driver handling
    """
    Represents a strategy which places a target into a requested state by
    calling specific drivers. A strategy usually needs to know some details of
    a given target.

    Life cycle:
    - create
    - bind (n times)
    - usage

    TODO: This might also be just a driver?
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target is None:
            raise BindingError(
                "Strategies can only be created on a valid target"
            )

    def on_client_bound(self, client):
        raise NotImplementedError("Strategies do not support clients")

    def on_activate(self):
        raise NotImplementedError("Strategies can not be activated")

    def on_deactivate(self):
        pass

    def resolve_conflicts(self, client):
        raise NotImplementedError("Strategies do not support clients")
