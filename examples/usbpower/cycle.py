from labgrid import Target
from labgrid.resource import USBPowerPort
from labgrid.driver import USBPowerDriver


t = Target(name="main")
upp = USBPowerPort(t, name=None, match={"ID_PATH": "pci-0000:00:14.0-usb-0:2:1.0"}, index=1)
upd = USBPowerDriver(t, name=None)

t.activate(upd)

print("Target:", t)
print("  Resources:", t.resources)
print("  Drivers:", t.drivers)
print("Status:", upd.get())

print("\n=== Switching power OFF ===")
upd.off()
print("Status:", upd.get())

print("\n=== Switching power ON ===")
upd.on()
print("Status:", upd.get())
