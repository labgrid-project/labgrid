import argparse
import logging
import sys
import textwrap
import time

from .udev import (
    USBSerialPort,
    USBMassStorage,
    USBTMC,
    USBVideo,
    IMXUSBLoader,
    AndroidUSBFastboot,
    DFUDevice,
    USBSDMuxDevice,
    USBSDWireDevice,
    AlteraUSBBlaster,
    RKUSBLoader,
    USBNetworkInterface,
    SiSPMPowerPort,
    USBAudioInput,
    LXAUSBMux,
    HIDRelay,
    USBDebugger,
    USBPowerPort,
    MatchedSysfsGPIO
)
from ..util import dump


class Suggester:
    def __init__(self, args):
        self.resources = []
        self.log = logging.getLogger("suggester")

        args = {
            'target': None,
            'name': None,
            'suggest': self.suggest_callback,
        }

        self.resources.append(USBSerialPort(**args))
        self.resources.append(USBTMC(**args))
        self.resources.append(USBVideo(**args))
        self.resources.append(IMXUSBLoader(**args))
        self.resources.append(AndroidUSBFastboot(**args))
        self.resources.append(DFUDevice(**args))
        self.resources.append(USBMassStorage(**args))
        self.resources.append(USBSDMuxDevice(**args))
        self.resources.append(USBSDWireDevice(**args))
        self.resources.append(AlteraUSBBlaster(**args))
        self.resources.append(RKUSBLoader(**args))
        self.resources.append(USBNetworkInterface(**args))
        self.resources.append(SiSPMPowerPort(**args))
        self.resources.append(USBAudioInput(**args))
        self.resources.append(LXAUSBMux(**args))
        self.resources.append(HIDRelay(**args))
        self.resources.append(USBDebugger(**args))
        self.resources.append(USBPowerPort(**args, index=0))
        self.resources.append(MatchedSysfsGPIO(**args, pin=0))

    def suggest_callback(self, resource, meta, suggestions):
        cls = type(resource).__name__
        if resource.device.action == 'add':
            print("=== added device ===")
        else:
            print("=== existing device ===")
        print(f"  {cls} for {resource.device.device_path}")

        if meta:
            print("  === device properties ===")
        for k, v in meta.items():
            print(f"  {k}: {v}")
        if not suggestions:
            print("  === no suggested matches found ===")
            print()
            return

        print("  === suggested matches ===")
        for i, suggestion in enumerate(suggestions):
            if i:
                print("  ---")
            print(textwrap.indent(
                dump({cls: {"match": suggestion}}).strip(),
                '  ',
            ))
            if cls == 'USBPowerPort':
                print('    index: ?')
            if cls == 'MatchedSysfsGPIO':
                print('    pin: ?')
        print("  ---")
        print()

    def run(self):
        while True:
            managers = {r.get_managed_parent().manager for r in self.resources}
            for manager in managers:
                manager.poll()
            time.sleep(0.1)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)7s %(name)-20s %(message)s',
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        default=False,
        help="enable debug mode"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    suggester = Suggester(args)
    try:
        suggester.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
