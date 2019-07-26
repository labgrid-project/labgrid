import sys
import labgrid
import logging
import time

from labgrid import Environment, StepReporter
from labgrid.driver.gpiodriver import GpioDigitalOutputDriver

# enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)

# show labgrid steps on the console
StepReporter()

t = labgrid.Target('main')
r = labgrid.resource.base.SysfsGPIO(t, name=None, index=60)
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
