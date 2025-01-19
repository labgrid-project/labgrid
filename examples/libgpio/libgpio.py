import logging
import time

from labgrid import Target
from labgrid.logging import basicConfig, StepLogger
from labgrid.driver import LibGPIODigitalOutputDriver
from labgrid.resource import LibGPIO

# enable info logging
basicConfig(level=logging.INFO)

# show labgrid steps on the console
StepLogger.start()

t = Target("main")
r = LibGPIO(t, name=None, gpiochip="/dev/gpiochip0", line=10, active_low=True)
d = LibGPIODigitalOutputDriver(t, name=None)

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

