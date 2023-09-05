from time import sleep

from labgrid import Target
from labgrid.driver import LauterbachDriver
from labgrid.resource import NetworkLauterbachDebugger

t = Target(name="main")

x50 = NetworkLauterbachDebugger(
    t,
    name=None,
    node="E22120045734",
    protocol="TCP"
)
t32 = LauterbachDriver(t, name=None, t32_sys="~/t32")

t.activate(t32)

# Set up target and trigger breakpoint
print("Opening Remote API connection")
t32.execute([
    'DO blackpill.cmm "TERM=ON"',
    "WAIT 2.s",
    r"Break.Set \\zephyr\main\102",
    "Go",
    'TERM.OUT "hello" 0xa',
])

sleep(1)

# Check target state
rcl = t32.control()
bp = rcl.fnc.address_offset(rcl.address.from_string(rcl.fnc.symbol_begin(r'\\zephyr\main\102')))
pc = rcl.fnc.register('PC')

assert pc == bp
print("Target halted at breakpoint")

print("Remote API connection closed")
rcl.disconnect
