#!/usr/bin/env python3
"""Capture Channel D1 of an fx2lafw device for 1 second."""

import sys
import time
import logging

from labgrid import Environment
from labgrid.logging import basicConfig

# enable info logging
basicConfig(level=logging.INFO)

env = Environment(sys.argv[1])
target = env.get_target("main")

sigrok = target.get_driver("SigrokDriver")
sigrok.capture("test.cap")
time.sleep(1)
sigrok.stop()
