#!/usr/bin/env python3

import argparse
import logging
import os

from labgrid.logging import basicConfig, StepLogger
from labgrid import Environment


def main(args):
    basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    StepLogger.start()

    env = Environment(config_file=args.config)
    target = env.get_target()
    qemu = target.get_driver("QEMUDriver", activate=False)

    if args.state:
        strategy = target.get_driver("Strategy")
        strategy.transition(args.state)
    else:
        print("No state given, skipping Strategy state transition")
        target.activate(qemu)
        qemu.on()

    qemu.interact()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run QEMU, either by activating the QEMUDriver directly or by transitioning into a strategy state first, then start a console."
    )
    parser.add_argument(
        "-c",
        "--config",
        default=os.environ.get("LG_ENV"),
        help="Environment config file to use (alternatively provided via LG_ENV)",
    )
    parser.add_argument(
        "-s",
        "--state",
        default=os.environ.get("LG_STATE"),
        help="State to transition the strategy into (alternatively provided via LG_STATE",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity",
    )

    args = parser.parse_args()

    if not args.config:
        parser.error("One of -c, --config or LG_ENV must be specified")

    main(args)
