from importlib import import_module
import attr

from ..factory import target_factory
from .common import Driver

@target_factory.reg_driver
@attr.s(eq=False)
class XenaDriver(Driver):
    """
    Xena Driver
    """
    bindings = {"xena_manager": "XenaManager"}

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._xena_app = import_module('xenavalkyrie.xena_app')
        self._tgn_utils = import_module('trafficgenerator.tgn_utils')
        self._xm = None

    def on_activate(self):
        self._xm = self._xena_app.init_xena(self._tgn_utils.ApiType.socket, self.logger, 'labgrid')
        self._xm.session.add_chassis(self.xena_manager.hostname)

    def on_deactivate(self):
        if self._xm:
            self._xm.session.disconnect()
            self._xm = None

    @Driver.check_active
    def get_session(self):
        return self._xm.session
