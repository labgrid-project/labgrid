#!/usr/bin/env python3
"""Capture Channel D1 of an fx2lafw device for 1 second."""

import sys
import time
import logging

from labgrid import Environment

# enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)

env = Environment(sys.argv[1])
target = env.get_target('main')

sigrok = target.get_driver("SigrokDriver")
sigrok.capture("test.cap")
time.sleep(1)
sigrok.stop()
