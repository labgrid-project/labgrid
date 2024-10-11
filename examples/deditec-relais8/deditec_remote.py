import logging
import time

from labgrid import Environment
from labgrid.logging import basicConfig, StepLogger

# enable info logging
basicConfig(level=logging.INFO)

# show labgrid steps on the console
StepLogger.start()

e = Environment("import-dedicontrol.yaml")
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
