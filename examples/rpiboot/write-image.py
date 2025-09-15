# script for automating the use of labgrid to write a new image to a raspberry pi
# using rpiboot.
# input place to write new image to and path to image.

import os
import sys
from time import sleep
from labgrid import Environment
from labgrid.driver import USBStorageDriver
from labgrid.driver import DigitalOutputPowerDriver
from labgrid.driver import DigitalOutputResetDriver
from labgrid.driver import RpibootDriver

image_path = sys.argv[1]

# if there is a 3. argument set is as the place labgrid should use.
# if not set the current value for LG_PLACE is used.
if len(sys.argv) >= 3:
    os.environ["LG_PLACE"] = sys.argv[2]

if os.environ.get("LG_PLACE", None) is None:
    print("No place to write image to given, set one with LG_PLACE or giving it as an extra argument")
    exit(1)

config_path = os.path.dirname(__file__) + "client.yaml"
env = Environment(config_path)
t = env.get_target("main")

power = t.get_driver("DigitalOutputPowerDriver")
t.activate(power)
gpio_reset = t.get_driver("GpioDigitalOutputDriver", name="reset-driver")
t.activate(gpio_reset)

# put panel into usbboot mode.
power.off()
gpio_reset.set(True)
sleep(1)
power.on()

# use rpiboot to enable MSD mode
rpiboot = RpibootDriver(t, name=None)
t.activate(rpiboot)
rpiboot.enable()

# wait a little bit to make sure the MSD is available.
sleep(5)

# write new image to panel
storage = USBStorageDriver(t, name=None)
t.activate(storage)
storage.write_image(filename=image_path)

# switch panel back into normal bootmode.
power.off()
gpio_reset.set(False)
sleep(1)
power.on()
