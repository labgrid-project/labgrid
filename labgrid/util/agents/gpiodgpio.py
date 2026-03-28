"""
This module implements switching GPIOs via descriptor based libgpiod interface.

Takes an integer property 'offset' which refers to the GPIO device. Figures out the gpiochip.

    ...
      - GpiodDigitalOutputDriver: {}
    ...
"""
import logging
import os
import subprocess
import re
import shutil
import time

class GpiodDigitalOutput:
    @staticmethod
    def find_gpiochip_by_offset(offset):
        output = subprocess.check_output(["/usr/bin/gpiodetect"], text=True)
        try:
            for line in output.strip().split('\n'):
                match = re.search(r'(gpiochip\d+)\s+\[.*\]\s+\((\d+)\s+lines\)', line)
                if match:
                    chip_name = match.group(1)
                    num_lines = int(match.group(2))
                    if 0 <= offset < num_lines:
                        return chip_name
        except Exception as e:
            raise RuntimeError(f"Failed to search for gpiochip: {e}")
        raise RuntimeError(f"Failed to search for gpiochip: {offset} not found")

    def _get_running_pid(self, value=None):
        try:
            # e.g. expect: 'gpiochip0 --consumer labgrid_6 6 1',
            # match: 'gpiochip0 --consumer labgrid_6 6 '
            # make sure to match surrounded by ' ', we do not want to match 16 or 26
            # note, former verion of gpio utils v1.x used '=' and different arguments
            pattern = f"gpioset.*-z.*-c {self.gpiochip}.* {self.offset} "
            if value is not None:
                pattern += str(value)
            output = subprocess.check_output(["pgrep", "-fa", pattern], text=True)
            # pgrep -a returns 'PID command...', we want the PID (first field)
            return output.splitlines()[0].split()[0]
        except subprocess.CalledProcessError:
            return None

    def __init__(self, offset):
        self._logger = logging.getLogger("Device: ")
        gpioset_path = shutil.which("gpioset")
        if not gpioset_path:
            raise RuntimeError("Failed, gpiod utils (gpioset) are not installed on the Exporter")
        try:
            version_output = subprocess.check_output(["gpioset", "-v"], stderr=subprocess.STDOUT, text=True)
            # match 'v' followed by digits e.g. v2.2.1
            match = re.search(r"v(\d+)\.", version_output)
            if not match or int(match.group(1)) < 2:
                raise RuntimeError(f"Failed, gpiod utils require version 2.x or higher (found: {version_output.splitlines()[0]})")
        except (subprocess.CalledProcessError, ValueError) as e:
            raise RuntimeError(f"Failed to check gpioset version: {e}")
        self.offset = offset
        self.gpiochip = GpiodDigitalOutput.find_gpiochip_by_offset(offset)

    def __del__(self):
        pass

    def get(self) -> bool:
        try:
            if self._get_running_pid(value=1):
                return True

            if self._get_running_pid(value=0):
                return False
        except Exception as e:
            return False
        return False

    def set(self, status: bool):
        val = 1 if status else 0
        opposing_val = 0 if status else 1

        # check if already in correct state
        if self._get_running_pid(value=val):
            self._logger.debug("GPIO %d has already correct state: %d, skipping", self.offset, val)
            return

        # check if holding GPIO in the opposing state
        opposing_pid = self._get_running_pid(value=opposing_val)
        if opposing_pid:
            self._logger.debug("GPIO %d is already claimed, trying to claim forced", self.offset)
            subprocess.run(["kill", "-15", opposing_pid])
            # wait for kernel to release the line (mandatory to avoid EBUSY)
            time.sleep(0.1)

        # now, set the new state
        try:
            subprocess.run(["/usr/bin/gpioset", "-z", "-c", self.gpiochip,
                "--consumer", f"labgrid_{self.offset}",
                f"{self.offset}={val}"
            ], check=True)
            self._logger.debug("GPIO %d set to %d", self.offset, val)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to claim GPIO {self.offset}: {e}")


_gpios = {}


def _get_gpio_line(offset):
    global _gpios
    if offset not in _gpios:
        _gpios[offset] = GpiodDigitalOutput(offset=offset)
    return _gpios[offset]

def handle_set(offset, status):
    gpio_line = _get_gpio_line(offset)
    gpio_line.set(status)

def handle_get(offset):
    gpio_line = _get_gpio_line(offset)
    return gpio_line.get()

def handle_cleanup(offset):
    pattern = f"gpioset.*{offset} "
    subprocess.run(["pkill", "-f", pattern])

methods = {
    'set': handle_set,
    'get': handle_get,
    'cleanup': handle_cleanup,
}
