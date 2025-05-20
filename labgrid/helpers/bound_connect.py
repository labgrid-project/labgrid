#!/usr/bin/python3 

# This is intended to be used via sudo. For example, add via visudo:
# %developers ALL = NOPASSWD: /usr/local/bin/labgrid-bound-connect

import argparse
import os
import sys
import ipaddress
import subprocess


def main(ifname, address, port):
    if not ifname:
        raise ValueError("Empty interface name.")
    if any((c == "/" or c.isspace()) for c in ifname):
        raise ValueError(f"Interface name '{ifname}' contains invalid characters.")
    if len(ifname) > 16:
        raise ValueError(f"Interface name '{ifname}' is too long.")

    address = ipaddress.ip_address(address)

    if not 0 < port < 0xFFFF:
        raise ValueError(f"Invalid port '{port}'.")

    args = [
        "socat",
        "STDIO",
    ]

    if address.version == 4:
        prefix = f"TCP4:{address}:{port}"
    elif address.version == 6:
        prefix = f"TCP6:[{address}]:{port}"
    else:
        raise RuntimeError(f"Invalid IP version '{address.version}'")

    # Delete the IP lookup cache for the address in case it is stale
    subprocess.run(["ip", "neigh", "del", str(address), "dev", ifname], 
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    args.append(','.join([
        prefix,
        f'so-bindtodevice={ifname}',
        'connect-timeout=15',
        'keepalive',
        'keepcnt=3',
        'keepidle=15',
        'keepintvl=15',
        'nodelay',
    ]))

    try:
        os.execvp(args[0], args)
    except FileNotFoundError as e:
        raise RuntimeError("Missing socat binary") from e


def main_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        default=False,
        help="enable debug mode"
    )
    parser.add_argument('interface', type=str, help='interface name')
    parser.add_argument('address', type=str, help='destination IP address')
    parser.add_argument('port', type=int, help='destination TCP port')
    args = parser.parse_args()
    try:
        main(args.interface, args.address, args.port)
    except Exception as e:  # pylint: disable=broad-except
        if args.debug:
            import traceback
            traceback.print_exc()
        print(f"ERROR: {e}", file=sys.stderr)

if __name__ == "__main__":
    main_args()
