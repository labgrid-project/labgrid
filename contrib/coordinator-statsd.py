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
# All metrics are optionally prefixed by a set of tag values which can be
# specified with the --tag command line option.
#
# This program will connect to a labgrid coordinator and report the following
# stats about places to a statsd server on a periodic basis:
#
#   labgrid.places.[TAG[.TAG]].acquired (gauge): The number of places that are
#                                                currently acquired with this
#                                                set of tags
#   labgrid.places.[TAG[.TAG]].total (gauge): The number of places attached to
#                                             the coordinator with this set of
#                                             tags
#
# It also can report metrics about reservations with the following format:
#
#   labgrid.reservations.GROUP.[TAG[.TAG]].STATE (gauge): The number of
#                                                         reservations in the
#                                                         given STATE
#
# where:
#   GROUP is the name of the filter group used for the reservation. Currently,
#   just "main"
#
#   STATE is the state of the reservation, e.g. "acquired", "waiting", etc.


import sys
import argparse
import os
import time
import asyncio

from labgrid.remote.client import start_session, Error
from labgrid.remote.generated import labgrid_coordinator_pb2
from labgrid.remote.common import Reservation
import statsd


def inc_gauge(gauges, key):
    gauges.setdefault(key, 0)
    gauges[key] += 1


async def report_reservations(session, tags, gauges):
    request = labgrid_coordinator_pb2.GetReservationsRequest()

    response = await session.stub.GetReservations(request)
    reservations = [Reservation.from_pb2(x) for x in response.reservations]

    for reservation in reservations:
        groups = reservation.filters

        if not groups:
            groups = {"": {}}

        for group_name, group in groups.items():
            inc_gauge(
                gauges,
                ".".join(
                    ["reservations", group_name]
                    + [group.get(t, "") for t in tags]
                    + [reservation.state.name]
                ),
            )


async def report_places(session, tags, gauges):
    acquired_count = 0
    total_count = 0

    for name, place in session.places.items():
        prefix = ".".join(["places"] + [place.tags.get(t, "") for t in tags])
        inc_gauge(gauges, f"{prefix}.total")
        if place.acquired:
            inc_gauge(gauges, f"{prefix}.acquired")


def main():
    parser = argparse.ArgumentParser(
        description="Report Labgrid usage metrics to statsd"
    )
    parser.add_argument(
        "-x",
        "--coordinator",
        metavar="ADDRESS",
        help="Coordinator address as HOST[:PORT]. Default is %(default)s",
        default=os.environ.get("LG_COORDINATOR", "127.0.0.1:20408"),
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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    statsd_client = None
    gauges = {}

    next_time = time.monotonic()

    while True:
        if statsd_client is None:
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

        # Reset all known gauges to 0
        for key in gauges:
            gauges[key] = 0

        sleep_time = next_time - time.monotonic()
        if sleep_time > 0:
            time.sleep(sleep_time)

        next_time = time.monotonic() + args.period
        try:
            session = start_session(args.coordinator, loop=loop)
            try:
                loop.run_until_complete(
                    asyncio.gather(
                        report_places(session, args.tags, gauges),
                        report_reservations(session, args.tags, gauges),
                    )
                )
            finally:
                loop.run_until_complete(session.stop())
                loop.run_until_complete(session.close())
        except Error as e:
            print(f"Error communicating with labgrid: {e}")
            continue

        try:
            with statsd_client.pipeline() as pipe:
                for k, v in gauges.items():
                    pipe.gauge(k, v)
        except OSError as e:
            print(f"Error communication with statsd server: {e}")
            statsd_client = None
            continue


if __name__ == "__main__":
    sys.exit(main())
