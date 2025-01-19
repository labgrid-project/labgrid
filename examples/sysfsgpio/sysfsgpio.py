import logging
import time

from labgrid import Target
from labgrid.logging import basicConfig, StepLogger
from labgrid.driver import GpioDigitalOutputDriver
from labgrid.resource import SysfsGPIO

# enable info logging
basicConfig(level=logging.INFO)

# show labgrid steps on the console
StepLogger.start()

t = Target("main")
r = SysfsGPIO(t, name=None, index=60, active_low=True)
d = GpioDigitalOutputDriver(t, name=None)

p = t.get_driver("DigitalOutputProtocol")
print(t.resources)
print("Testing IO")
p.set(True)
print(p.get())
time.sleep(2)
p.set(False)
print(p.get())
time.sleep(2)
p.set(True)
print(p.get())
time.sleep(2)
p.invert()
print(p.get())
time.sleep(2)
p.invert()
print(p.get())
time.sleep(2)

print("Testing Power")
p.off()
print(p.get())
time.sleep(2)
p.on()
print(p.get())
time.sleep(2)
p.cycle()
print(p.get())
time.sleep(2)

print("Testing Button")
p.release()
print(p.get())
time.sleep(2)
p.press()
print(p.get())
time.sleep(2)
p.release()
print(p.get())
time.sleep(2)
p.press_for()
print(p.get())

