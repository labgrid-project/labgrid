#! /usr/bin/env python3
#
# Copyright 2022 Garmin Ltd. or its subsidiaries
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# This program will connect to a labgrid coordinator and report the following
# stats about places to a statsd server on a periodic basis:
#
#   labgrid.places_acquired (set): The number of places that are currently
#                                  acquired
#   labgrid.places_total (set): The number of places attached to the
#                               coordinator
#
# It also can report metrics about reservations with the following format:
#
#   labgrid.reservations.GROUP.[TAG[.TAG]].STATE (set): The number of
#                                                      reservations in the
#                                                      given STATE
#
# where:
#   GROUP is the name of the filter group used for the reservation. Currently,
#   just "main"
#
#   TAG is values of the tags of interest. You can specify which tag values are
#   shown with the --tag command-line option
#
#   STATE is the state of the reservation, e.g. "acquired", "waiting", etc.


import sys
import argparse
import statsd
import os
import labgrid.remote.client
import time


async def report_reservations(session, statsd_client, tags):
    reservations = await session.call("org.labgrid.coordinator.get_reservations")

    for token, config in reservations.items():
        state = config["state"]

        groups = config.get("filters", {})

        if not groups:
            groups = {"": {}}

        for group_name, group in groups.items():
            path = (
                ["reservations", group_name]
                + [group.get(t, "") for t in tags]
                + [state]
            )
            statsd_client.set(".".join(path), token)


async def report_places(session, statsd_client):
    acquired_count = 0
    total_count = 0

    for name, place in session.places.items():
        statsd_client.set("places_total", name)
        if place.acquired:
            statsd_client.set("places_acquired", name)


async def report(session, statsd_client, tags):
    await report_reservations(session, statsd_client, tags)
    await report_places(session, statsd_client)


def main():
    parser = argparse.ArgumentParser(
        description="Report Labgrid usage metrics to statsd"
    )
    parser.add_argument(
        "-x",
        "--crossbar",
        metavar="URL",
        help="Crossbar URL for the coordinator",
        default=os.environ.get("LG_CROSSBAR", "ws://127.0.0.1:20408/ws"),
    )
    parser.add_argument(
        "--period",
        help="How often to report reservations stats to statsd. Default is %(default)s",
        type=int,
        default=60,
    )
    parser.add_argument(
        "--statsd-protocol",
        metavar="PROTOCOL",
        choices=("udp", "tcp"),
        default="udp",
        help="Use specified protocol for statsd",
    )
    parser.add_argument(
        "--statsd-prefix",
        metavar="PREFIX",
        help="Prefix for statsd stats",
        default="labgrid",
    )
    parser.add_argument(
        "--statsd-server",
        metavar="HOST",
        help="Statsd server",
        default="localhost",
    )
    parser.add_argument(
        "--statsd-port",
        metavar="PORT",
        help="Statsd server port",
        type=int,
        default=8125,
    )
    parser.add_argument(
        "--tag",
        metavar="TAG",
        dest="tags",
        help="Tag values to include in statsd path for reservations. Repeat to include multiple tags",
        action="append",
        default=[],
    )

    args = parser.parse_args()

    if args.statsd_protocol == "udp":
        statsd_client = statsd.StatsClient(
            host=args.statsd_server,
            port=args.statsd_port,
            prefix=args.statsd_prefix,
        )
    elif args.statsd_protocol == "tcp":
        statsd_client = statsd.TCPStatsClient(
            host=args.statsd_server,
            port=args.statsd_port,
            prefix=args.statsd_prefix,
        )

    while True:
        next_time = time.monotonic() + args.period
        extra = {}
        session = labgrid.remote.client.start_session(
            args.crossbar,
            os.environ.get("LG_CROSSBAR_REALM", "realm1"),
            extra,
        )

        with statsd_client.pipeline() as pipe:
            session.loop.run_until_complete(report(session, pipe, args.tags))

        sleep_time = next_time - time.monotonic()
        if sleep_time > 0:
            time.sleep(sleep_time)


if __name__ == "__main__":
    sys.exit(main())
