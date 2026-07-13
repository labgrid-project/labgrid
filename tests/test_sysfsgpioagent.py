import pytest

import os
from labgrid.util.agents import sysfsgpio
from labgrid.util.agents.sysfsgpio import GpioDigitalOutput
from tempfile import TemporaryDirectory

class TestGpioAgent:

    class GpioDigitalOutputMock(GpioDigitalOutput):
        def __init__(self, **kwargs):
            index = kwargs['index']
            self.sysfs_mock_directory = TemporaryDirectory()
            GpioDigitalOutput._gpio_sysfs_path_prefix = self.sysfs_mock_directory.name
            export_file_path = os.path.join(self.sysfs_mock_directory.name, 'export')
            os.mknod(export_file_path)
            # Since there is no real device, writing to `export` does not create a corresponding
            # control directory. Expect a value error to be raised.
            with pytest.raises(ValueError, match='Device not found'):
                super().__init__(**kwargs)
            with open(export_file_path, mode='r') as export_file:
                export_content = export_file.readline()
                assert export_content == str(index)
            self.gpio_line_directory = os.path.join(self.sysfs_mock_directory.name, f'gpio{index}')
            os.mkdir(self.gpio_line_directory)
            for control_file in ['active_low', 'direction', 'value']:
                control_file_path = os.path.join(self.gpio_line_directory, control_file)
                print(f'creating control file `{control_file_path}`')
                os.mknod(control_file_path)
            super().__init__(**kwargs)

        def set(self, val):
            # new values are available at the beginning of the virtual file
            # emulate this behavior
            os.lseek(self.gpio_sysfs_value_fd, 0, os.SEEK_SET)
            super().set(val)

    def test_instantiation(self):
        gpio_line = TestGpioAgent.GpioDigitalOutputMock(index=13, invert=False)
        assert isinstance(gpio_line, GpioDigitalOutput)

    def test_set(self):
        gpio_line = TestGpioAgent.GpioDigitalOutputMock(index=13, invert=False)
        for val in [True, False, True, False]:
            gpio_line.set(val)
            assert gpio_line.get() == val

    def test_output_direction(self):
        gpio_line = TestGpioAgent.GpioDigitalOutputMock(index=13, invert=False)
        direction_file_path = os.path.join(gpio_line.gpio_line_directory, 'direction')
        with open(direction_file_path, mode='rb') as direction_file:
            assert direction_file.read() == b'out'

    def test_input_direction(self):
        gpio_line = TestGpioAgent.GpioDigitalOutputMock(index=13, invert=False, direction='in')
        direction_file_path = os.path.join(gpio_line.gpio_line_directory, 'direction')
        value_file_path = os.path.join(gpio_line.gpio_line_directory, 'value')

        with open(direction_file_path, mode='rb') as direction_file:
            assert direction_file.read() == b'in'

        with open(value_file_path, mode='wb') as value_file:
            value_file.write(b'1')

        assert gpio_line.get() is True

    def test_invalid_direction(self):
        with pytest.raises(ValueError, match='direction'):
            GpioDigitalOutput(index=13, invert=False, direction='invalid')

    def test_cached_line_reconfigures_direction(self):
        with TemporaryDirectory() as sysfs_mock_directory:
            GpioDigitalOutput._gpio_sysfs_path_prefix = sysfs_mock_directory
            sysfsgpio._gpios.clear()
            gpio_line_directory = os.path.join(sysfs_mock_directory, 'gpio13')
            os.mkdir(gpio_line_directory)
            for control_file in ['active_low', 'direction', 'value']:
                os.mknod(os.path.join(gpio_line_directory, control_file))

            sysfsgpio.handle_set(13, False, True)
            sysfsgpio.handle_get(13, False, 'in')
            sysfsgpio.handle_set(13, False, False)

            direction_file_path = os.path.join(gpio_line_directory, 'direction')
            with open(direction_file_path, mode='rb') as direction_file:
                assert direction_file.read() == b'out'
