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

e = labgrid.Environment('import-dedicontrol.yaml')
t = e.get_target()

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
