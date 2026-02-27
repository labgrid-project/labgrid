import logging
import time

from labgrid import Target
from labgrid.logging import basicConfig, StepLogger
from labgrid.driver import GpioDigitalOutputDriver
from labgrid.resource import ManagedGPIO

# enable info logging
basicConfig(level=logging.INFO)

# show labgrid steps on the console
StepLogger.start()

t = Target("main")
r = ManagedGPIO(t, name=None, chip="/dev/gpiochip0", pin=0)
d = GpioDigitalOutputDriver(t, name=None)

p = t.get_driver("DigitalOutputProtocol")
print(t.resources)
p.set(True)
print(p.get())
time.sleep(2)
p.set(False)
print(p.get())
time.sleep(2)
p.set(True)
print(p.get())
