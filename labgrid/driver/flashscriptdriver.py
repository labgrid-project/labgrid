import attr

from ..factory import target_factory
from ..step import step
from ..util.managedfile import ManagedFile
from .common import Driver

from ..util.helper import processwrapper


@target_factory.reg_driver
@attr.s(eq=False)
class FlashScriptDriver(Driver):
    bindings = {
        "device": {
            "USBFlashableDevice",
            "NetworkUSBFlashableDevice",
        },
    }
    script = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    args = attr.ib(
        default=attr.Factory(list),
        validator=attr.validators.optional(attr.validators.instance_of(list)),
    )

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=["script"])
    def flash(self, script=None, args=None):
        """
        Transfers and remotely executes the script

        Args:
            script (str): optional, path to the script to write to bound Flashable Device
        """
        if script is None and self.script is not None:
            script = self.target.env.config.get_image_path(self.script)
        assert script, "flash requires a script"

        if args is None:
            args = self.args

        mf = ManagedFile(script, self.device)
        mf.sync_to_resource()

        cmd = [mf.get_remote_path()] + [a.format(device=self.device, file=mf) for a in args]

        self.logger.debug("Running command '%s'", " ".join(cmd))
        processwrapper.check_output(
            self.device.command_prefix + cmd, print_on_silent_log=True
        )
