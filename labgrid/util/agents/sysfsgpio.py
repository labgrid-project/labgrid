"""
This module implements switching GPIOs via sysfs GPIO kernel interface.

Takes an integer property 'index' which refers to the already exported GPIO device.
Takes an boolean property 'active_low' which inverts logical values if set to True

"""
import logging
import warnings
import os

class GpioDigitalOutput:
    _gpio_sysfs_path_prefix = '/sys/class/gpio'

    @staticmethod
    def _assert_gpio_line_is_exported(index):
        gpio_sysfs_path = os.path.join(GpioDigitalOutput._gpio_sysfs_path_prefix,
                                       f'gpio{index}')
        # Deprecated: the exporter can export on acquire, we are leaving this
        # in for now to support exporters which have not been updated yet.
        if not os.path.exists(gpio_sysfs_path):
            export_sysfs_path = os.path.join(GpioDigitalOutput._gpio_sysfs_path_prefix, 'export')
            with open(export_sysfs_path, mode='wb') as export:
                export.write(str(index).encode('utf-8'))
        if not os.path.exists(gpio_sysfs_path):
            raise ValueError("Device not found")

    def __init__(self, index, active_low):
        self._logger = logging.getLogger("Device: ")
        GpioDigitalOutput._assert_gpio_line_is_exported(index)
        gpio_sysfs_path = os.path.join(GpioDigitalOutput._gpio_sysfs_path_prefix,
                                       f'gpio{index}')

        gpio_sysfs_direction_path = os.path.join(gpio_sysfs_path, 'direction')
        with open(gpio_sysfs_direction_path, 'rb') as direction_fd:
            literal_value = direction_fd.read(3)
        if literal_value != b"out":
            self._logger.debug("Configuring GPIO %d as output.", index)
            with open(gpio_sysfs_direction_path, 'wb') as direction_fd:
                direction_fd.write(b'out')

        gpio_sysfs_value_path = os.path.join(gpio_sysfs_path, 'value')
        self.gpio_sysfs_value_fd = os.open(gpio_sysfs_value_path, flags=(os.O_RDWR | os.O_SYNC))

        gpio_sysfs_active_low_path = os.path.join(gpio_sysfs_path, 'active_low')
        with open(gpio_sysfs_active_low_path, 'w') as active_low_fd:
            active_low_fd.write(str(int(active_low)))

    def __del__(self):
        os.close(self.gpio_sysfs_value_fd)
        self.gpio_sysfs_value_fd = None

    def get(self):
        os.lseek(self.gpio_sysfs_value_fd, 0, os.SEEK_SET)
        literal_value = os.read(self.gpio_sysfs_value_fd, 1)
        if literal_value == b'0':
            return False
        elif literal_value == b'1':
            return True
        raise ValueError("GPIO value is out of range.")

    def set(self, status):
        self._logger.debug("Setting GPIO to `%s`.", status)
        binary_value = None
        if status is True:
            binary_value = b'1'
        elif status is False:
            binary_value = b'0'

        if binary_value is None:
            raise ValueError("GPIO value is out of range.")

        os.write(self.gpio_sysfs_value_fd, binary_value)


_gpios = {}

def _get_gpio_line(index, active_low):
    if index not in _gpios:
        _gpios[index] = GpioDigitalOutput(index=index, active_low=active_low)
    return _gpios[index]

def handle_set(index, active_low, status):
    warnings.warn(
        "SysfsGPIO has been deprecated.  Please use LibGPIO.  See https://www.kernel.org/doc/Documentation/gpio/sysfs.txt",
        DeprecationWarning,
    )
    gpio_line = _get_gpio_line(index, active_low)
    gpio_line.set(status)


def handle_get(index, active_low):
    warnings.warn(
        "SysfsGPIO has been deprecated.  Please use LibGPIO.  See https://www.kernel.org/doc/Documentation/gpio/sysfs.txt",
        DeprecationWarning,
    )
    gpio_line = _get_gpio_line(index, active_low)
    return gpio_line.get()


methods = {
    'set': handle_set,
    'get': handle_get,
}
