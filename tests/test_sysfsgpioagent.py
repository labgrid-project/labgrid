import pytest

import os
from labgrid.util.agents.sysfsgpio import GpioDigitalOutput
from tempfile import TemporaryDirectory

class TestGpioAgent:

    class GpioDigitalOutputMock(GpioDigitalOutput):
        def __init__(self, **kwargs):
            index = kwargs['index']
            self.sysfs_mock_directory = TemporaryDirectory()
            GpioDigitalOutput._gpio_sysfs_path_prefix = self.sysfs_mock_directory.name
            GpioDigitalOutput._buffered_file_access = True
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
            for control_file in ['direction', 'value']:
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
        gpio_line = TestGpioAgent.GpioDigitalOutputMock(index=13)
        assert isinstance(gpio_line, GpioDigitalOutput)

    def test_set(self):
        gpio_line = TestGpioAgent.GpioDigitalOutputMock(index=13)
        for val in [True, False, True, False]:
            gpio_line.set(val)
            assert gpio_line.get() == val
