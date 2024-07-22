import sys
import logging
import time

from labgrid import StepReporter, Target
from labgrid.driver import GpioDigitalOutputDriver
from labgrid.resource import SysfsGPIO

# enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)

# show labgrid steps on the console
StepReporter.start()

t = Target('main')
r = SysfsGPIO(t, name=None, index=60)
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
