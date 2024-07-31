import attr
import time

from .common import Driver
from ..factory import target_factory
from ..step import step
from .exception import ExecutionError
from ..protocol import ResetProtocol, RecoveryProtocol
from ..util.helper import processwrapper
from .consoleexpectmixin import ConsoleExpectMixin

@target_factory.reg_driver
@attr.s(eq=False)
class ServoDriver(ConsoleExpectMixin, Driver):
    """Provides access to servo features including console and reset

    This driver provides an API to the dut-control program, allowing changes to
    be made to the servo settings.

    Args:
        bindings (dict): driver to use with
    """
    bindings = {
        'servo': {'Servo', 'NetworkServo'},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('dut-control')
        else:
            self.tool = 'dut-control'

    def dut_control(self, *args):
        """Run the dut-control tool

        Args:
            args (list of str): Argument sto pass to dut-control
        """
        cmd = self.servo.command_prefix + [
            self.tool,
            '-p', str(self.servo.port),
            *args,
        ]
        processwrapper.check_output(cmd)

    @Driver.check_active
    @step(title='do_reset', args=['delay', 'mode'])
    def do_reset(self, delay, mode='cold'):
        """Reset the device

        This creates a 200ms reset pulse on either cold-/warm-reset line.

        Args:
            mode (str): 'warm' or 'cold'
        """
        if not mode in ['warm', 'cold']:
            raise ExecutionError(
                f"Setting mode '{mode}' not supported by ServoDriver")
        self.dut_control(f'{mode}_reset:on', f'sleep:{delay:f}',
                         f'{mode}_reset:off')

    @Driver.check_active
    @step(title='set_reset_enable', args=['enable', 'mode'])
    def set_reset_enable(self, enable, mode='cold', delay=0.5):
        """Sets the state of the reset line

        If enable is False, a delay will be added before the line is changed.

        Args:
            enable (bool): True to enable reset, False to disable
        """
        if not enable:
            time.sleep(delay)
        state = 'on' if enable else 'off'
        self.dut_control(f'{mode}_reset:{state}')

    @Driver.check_active
    @step(title='set_recovery', args=['enable'])
    def set_recovery(self, enable):
        """Set the recovery-button state

        Args:
            enable (bool): True to enable recovery, False to disable
        """
        #self.dut_control('cold_reset:on', 'sleep:.5',
                         #'cold_reset:off', 'sleep:.5')
        #self.dut_control('warm_reset:on', 't20_rec:on', 'sleep:.2',
                         #'warm_reset:off', 'sleep:.5', 't20_rec:off')
        state = 'on' if enable else 'off'
        self.dut_control(f't20_rec:{state}')

    @Driver.check_active
    @step(title='get_tty')
    def get_tty(self):
        """Get the tty for the CPU (AP) UART

        Return:
            str: Device name, e.g. '/dev/pty/23'
        """
        pty = self.dut_control('cpu_uart_pty').strip().split(':')[1]
        print(f'{self.servo.serial}. is on port {self.servo.port} and uses {pty}')
        return pty

    def __str__(self):
        return f'ServoDriver({self.servo.serial})'


@target_factory.reg_driver
@attr.s(eq=False)
class ServoResetDriver(Driver, ResetProtocol):
    """Reset target using servo"""
    delay = attr.ib(default=0.2, validator=attr.validators.instance_of(float))

    bindings = {
        'reset_info': {'ServoReset', 'NetworkServoReset'},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step(title='reset', args=['mode'])
    @step()
    def reset(self, mode='cold'):
        servo = self.target.get_driver('ServoDriver')
        servo.do_reset(self.delay, mode)

    @Driver.check_active
    @step(title='set_reset_enable', args=['enable', 'mode'])
    def set_reset_enable(self, enable, mode='cold'):
        servo = self.target.get_driver('ServoDriver')
        servo.set_reset_enable(enable, mode, self.delay)

    def __str__(self):
        return f'ServoResetDriver({self.target.name})'


@target_factory.reg_driver
@attr.s(eq=False)
class ServoRecoveryDriver(Driver, RecoveryProtocol):
    """Recovery button using servo"""
    bindings = {
        'reset_info': {'ServoRecovery', 'NetworkServoRecovery'},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step()
    def set_enable(self, status):
        servo = self.target.get_driver('ServoDriver')
        servo.set_recovery(status)

    def __str__(self):
        return f'ServoRecoveryDriver({self.target.name})'
