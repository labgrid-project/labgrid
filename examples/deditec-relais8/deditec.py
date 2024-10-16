import logging
import time

from labgrid import Target
from labgrid.logging import basicConfig, StepLogger
from labgrid.resource.udev import DeditecRelais8
from labgrid.driver import DeditecRelaisDriver

# enable info logging
basicConfig(level=logging.INFO)

# log labgrid steps
StepLogger.start()

t = Target("main")
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
