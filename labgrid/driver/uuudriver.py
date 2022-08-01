import logging
import os
import attr

from ..factory import target_factory
from .common import Driver
from ..util.managedfile import ManagedFile
from ..util.helper import processwrapper


@target_factory.reg_driver
@attr.s(eq=False)
class UniversalUpdateUtilityDriver(Driver):
    bindings = {
        "uuu": {"NetworkUUU"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger(f"{self}({self.target})")

        if self.target.env:
            self.tool = self.target.env.config.get_tool('uuu') or 'uuu'
        else:
            self.tool = 'uuu'

    def _get_uuu_cmd(self, *args):
        if not hasattr(self.uuu, "extra"):
            setattr(self.uuu, "extra", {})
        self.uuu.extra["ssh_extra_args"] = ["-tq"]

        uuu_otg_path = []
        for usb_otg_path in self.uuu.usb_otg_path:
            uuu_otg_path.append("-m")
            uuu_otg_path.append(usb_otg_path)

        native_uuu_cmd = [self.tool] + uuu_otg_path + list(args)
        self.logger.info(" ".join(native_uuu_cmd))

        uuu_cmd = self.uuu.command_prefix + native_uuu_cmd

        return uuu_cmd

    @Driver.check_active
    def __call__(self, *args):
        processwrapper.check_output(
            self._get_uuu_cmd(*args),
            print_on_silent_log=True
        )

    @Driver.check_active
    def run(self, *args):
        def handle_args():
            for arg in args:
                if os.path.isfile(arg):
                    mf = ManagedFile(arg, self.uuu)
                    mf.sync_to_resource()
                    yield mf.get_remote_path()
                else:
                    yield arg

        self(*list(handle_args()))
