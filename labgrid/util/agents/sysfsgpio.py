"""
This module implements accessing GPIOs via sysfs GPIO kernel interface.

Takes an integer property 'index' which refers to the already exported GPIO device.
Takes a boolean property 'invert' which inverts logical values if set to True (active-low)

"""
import logging
import os


class GpioDigitalOutput:
    _gpio_sysfs_path_prefix = '/sys/class/gpio'
    _directions = {
        'in': b'in',
        'out': b'out',
    }

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

    def __init__(self, index, invert, direction='out'):
        self.gpio_sysfs_value_fd = None
        if direction not in self._directions:
            raise ValueError("GPIO direction is out of range.")

        self._logger = logging.getLogger("Device: ")
        GpioDigitalOutput._assert_gpio_line_is_exported(index)
        gpio_sysfs_path = os.path.join(GpioDigitalOutput._gpio_sysfs_path_prefix,
                                       f'gpio{index}')

        self.gpio_sysfs_direction_path = os.path.join(gpio_sysfs_path, 'direction')
        self.gpio_sysfs_active_low_path = os.path.join(gpio_sysfs_path, 'active_low')
        self.configure(index, invert, direction)

        gpio_sysfs_value_path = os.path.join(gpio_sysfs_path, 'value')
        flags = os.O_SYNC
        if direction == 'out':
            flags |= os.O_RDWR
        else:
            flags |= os.O_RDONLY
        self.gpio_sysfs_value_fd = os.open(gpio_sysfs_value_path, flags=flags)

    def configure(self, index, invert, direction):
        with open(self.gpio_sysfs_direction_path, 'rb') as direction_fd:
            literal_value = direction_fd.read(3).strip()
        if literal_value != self._directions[direction]:
            self._logger.debug("Configuring GPIO %d as %s.", index, direction)
            with open(self.gpio_sysfs_direction_path, 'wb') as direction_fd:
                direction_fd.write(self._directions[direction])

        with open(self.gpio_sysfs_active_low_path, 'w') as active_low_fd:
            active_low_fd.write(str(int(invert)))

    def __del__(self):
        if self.gpio_sysfs_value_fd is not None:
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

def _get_gpio_line(index, invert, direction):
    key = (index, invert, direction)
    if key not in _gpios:
        _gpios[key] = GpioDigitalOutput(index=index, invert=invert, direction=direction)
    else:
        _gpios[key].configure(index, invert, direction)
    return _gpios[key]

def handle_set(index, invert, status):
    gpio_line = _get_gpio_line(index, invert, 'out')
    gpio_line.set(status)


def handle_get(index, invert, direction='out'):
    gpio_line = _get_gpio_line(index, invert, direction)
    return gpio_line.get()

methods = {
    'set': handle_set,
    'get': handle_get,
}
