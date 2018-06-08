#!/usr/bin/env python3
"""Power-cycle a target until the /dev/nand0 device is missing."""

import sys
import logging

from labgrid import Environment, StepReporter
from labgrid.strategy.bareboxstrategy import Status


# enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)

# show labgrid steps on the console
StepReporter()

def run_once(target):
    s = target.get_driver('BareboxStrategy')
    s.status = Status.unknown  # force a power-cycle
    s.transition('barebox')
    cmd = target['CommandProtocol']
    cmd.run_check('test -e /dev/nand0')
    target.deactivate(cmd)

env = Environment(sys.argv[1])
target = env.get_target('main')
while True:
    run_once(target)
