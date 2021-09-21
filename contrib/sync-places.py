#! /usr/bin/env python3
#
# Copyright 2021 Garmin Ltd. or its subsidiaries
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

import argparse
from contextlib import contextmanager
from labgrid.remote.client import start_session
from labgrid.util.proxy import proxymanager
import os
import sys
import textwrap
import yaml


def main():
    @contextmanager
    def get_file(name, mode, standard):
        if name == "-":
            yield standard
        else:
            with open(name, mode) as f:
                yield f

    async def do_sync(session, args):
        with get_file(args.places, "r", sys.stdin) as f:
            config = yaml.safe_load(f)

        config.setdefault("places", {})

        changed = False
        seen_places = set()
        remove_places = set()
        for name, place in session.places.items():
            if name in config["places"]:
                seen_places.add(name)
            else:
                remove_places.add(name)

        for name in remove_places:
            print(f"Removing place {name}")
            if not args.dry_run:
                await session.call("org.labgrid.coordinator.del_place", name)
            changed = True

        for name in config["places"]:
            if not name in seen_places:
                print(f"Adding place {name}")
                if not args.dry_run:
                    await session.call("org.labgrid.coordinator.add_place", name)
                changed = True

        for name in config["places"]:
            matches = config["places"][name].get("matches", [])
            seen_matches = set()
            remove_matches = set()
            place_tags = {}
            if name in seen_places:
                place = session.places[name]
                for m in place.matches:
                    m = repr(m)
                    if m in matches:
                        seen_matches.add(m)
                    else:
                        remove_matches.add(m)
                place_tags = place.tags

            for m in remove_matches:
                print(f"Deleting match '{m}' for place {name}")
                if not args.dry_run:
                    await session.call(
                        "org.labgrid.coordinator.del_place_match", name, m
                    )
                changed = True

            for m in matches:
                if not m in seen_matches:
                    print(f"Adding match '{m}' for place {name}")
                    if not args.dry_run:
                        await session.call(
                            "org.labgrid.coordinator.add_place_match", name, m
                        )
                    changed = True

            tags = config["places"][name].get("tags", {}).copy()
            if place_tags != tags:
                print(
                    "Setting tags for place %s to %s"
                    % (
                        name,
                        ", ".join(
                            "%s=%s" % (key, value) for (key, value) in tags.items()
                        ),
                    )
                )

                # Set the empty string for tags that should be removed
                for k in place_tags:
                    if k not in tags:
                        tags[k] = ""

                if not args.dry_run:
                    await session.call(
                        "org.labgrid.coordinator.set_place_tags", name, tags
                    )
                changed = True

    async def do_dump(session, args):
        config = {"places": {}}
        for name, place in session.places.items():
            config["places"][name] = {
                "matches": [repr(m) for m in place.matches],
                "tags": {k: v for k, v in place.tags.items()},
            }

        with get_file(args.dest, "w", sys.stdout) as f:
            yaml.dump(config, f)

    parser = argparse.ArgumentParser(
        description="Synchronize Labgrid places",
        epilog=textwrap.dedent(
            """\
            The YAML files describe what places should exist and what match
            strings and tags should be assigned to those places. The files are
            structured like:

              places: # A dictonary of places where each key is a place name
                my-place1: # Replace with your place
                  matches: # A list of match patterns. Replace with your match patterns
                    - "*/my-place1/*"
                  tags: # A dictionary of key/value tags. Replace with your tags
                    board: awesomesauce
                    bar: baz

            When syncing places, tags, and matches will be added or removed until the
            remote configuration matches the one in the YAML file
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--crossbar",
        "-x",
        metavar="URL",
        default=os.environ.get("LG_CROSSBAR", "ws://127.0.0.1:20408/ws"),
        help="Crossbar websocket URL (default: %(default)s)",
    )
    parser.add_argument("--proxy", "-P", help="Proxy connections via given ssh host")

    subparsers = parser.add_subparsers()
    subparsers.required = True

    sync_parser = subparsers.add_parser(
        "sync", help="Synchronize coordinator places with file"
    )
    sync_parser.add_argument(
        "places",
        metavar="FILE",
        help="Places configuration YAML file. Use '-' for stdin",
    )
    sync_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Don't make any changes, only show what would be done",
    )
    sync_parser.set_defaults(func=do_sync)

    dump_parser = subparsers.add_parser(
        "dump",
        help="Dump existing places configuration to a YAML file. The dumped file is suitable for passing to `sync`",
    )
    dump_parser.add_argument(
        "dest",
        metavar="FILE",
        nargs="?",
        default="-",
        help="Destination file. Use '-' for stdout. Default is '%(default)s'",
    )
    dump_parser.set_defaults(func=do_dump)

    args = parser.parse_args()

    if args.proxy:
        proxymanager.force_proxy(args.proxy)

    session = start_session(
        args.crossbar, os.environ.get("LG_CROSSBAR_REALM", "realm1"), {}
    )

    return session.loop.run_until_complete(args.func(session, args))


if __name__ == "__main__":
    sys.exit(main())
