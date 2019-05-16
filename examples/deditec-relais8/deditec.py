import sys
import labgrid
import logging
import time

from labgrid import Environment, StepReporter
from labgrid.strategy.bareboxstrategy import Status
from labgrid.driver.deditecrelaisdriver import DeditecRelaisDriver

# enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)

# show labgrid steps on the console
StepReporter()

t = labgrid.Target('main')
r = labgrid.resource.udev.DeditecRelais8(t, name=None, index=1)
d = DeditecRelaisDriver(t, name=None)

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
