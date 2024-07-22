import sys
import logging
import time

from labgrid import Target, StepReporter
from labgrid.resource.udev import DeditecRelais8
from labgrid.driver import DeditecRelaisDriver

# enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)

# show labgrid steps on the console
StepReporter.start()

t = Target('main')
r = DeditecRelais8(t, name=None, index=1)
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
