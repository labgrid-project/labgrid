"""
Exporter Agent script executing raw pyftdi commands locally on the Raspberry Pi.
"""

import sys
import os
import time
import re

import logging
import io

from pyftdi.eeprom import FtdiEeprom
from pyftdi.misc import hexdump
from pyftdi.i2c import I2cController, I2cNackError
from pyftdi.jtag import JtagEngine
from pyftdi.bits import BitSequence

class FtdiMpsseAgent:
    def __init__(self):
        self._logger = logging.getLogger("FtdiMpsseAgent")

    def dump_eeprom(self, url: str) -> tuple:
        eeprom = FtdiEeprom()
        eeprom.open(url)
        config_summary = eeprom.dump_config()
        hex_dump_data = hexdump(eeprom.data)
        return config_summary, hex_dump_data

    def i2cdetect(self, url: str, mask: int, val: int) -> str:
        """Configures FTDI context lines, executes wake tokens, and scans the bus."""
        i2c = I2cController()
        out_stream = io.StringIO()

        try:
            i2c.configure(url, frequency=100e3) # 100kHz
            gpio = i2c.get_gpio()

            gpio.set_direction(mask, mask)
            gpio.write(val)
            time.sleep(0.05)

            try:
                i2c.get_port(0x00).write([0x00])
            except I2cNackError:
                pass
            time.sleep(0.003)

            out_stream.write("     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f\n")
            for row in range(0, 128, 16):
                out_stream.write(f"{row:02x}:")
                for col in range(16):
                    addr = row + col

                    # Skip invalid system reserved boundaries
                    if addr < 0x03 or addr > 0x77:
                        out_stream.write("   ")
                        continue

                    try:
                        port = i2c.get_port(addr)
                        port.read(0)  # Minimal zero-byte transaction read probe
                        out_stream.write(f" {addr:02x}")
                    except I2cNackError:
                        out_stream.write(" --")
                    except Exception:
                        out_stream.write(" ??")
                out_stream.write("\n")

        except Exception as e:
            raise RuntimeError(f"Bus scan failed (is the device powered?): {e}")
        finally:
            i2c.terminate()
        return out_stream.getvalue()

    def i2ctransfer(self, url: str, mask: int, val: int, args: list) -> str:
        """Parses action parameters and executes multi-stage I2C transactions on the Pi."""
        if not args or len(args) < 2:
            return "Usage: lc ftdi i2ctransfer <i2c_addr> <action_1> [data_bytes...] [action_2] ..."

        def parse_int(val_str):
            return int(val_str, 16) if val_str.lower().startswith('0x') else int(val_str)

        try:
            target_addr = parse_int(args[0])
        except ValueError:
            return f"Error: Invalid I2C target address token: {args[0]}"

        # Parse actions array (e.g. ['w1', '0x0C', 'r4'])
        action_pattern = re.compile(r'^([wrWR])(\d+)$')
        actions_queue = []
        action_args = args[1:]

        idx = 0
        while idx < len(action_args):
            match = action_pattern.match(action_args[idx])
            if not match:
                return f"Syntax error parsing action token: {action_args[idx]}"

            mode = match.group(1).lower()
            count = int(match.group(2))

            if mode == 'w':
                if idx + count >= len(action_args):
                    return f"Error: Action '{action_args[idx]}' expects {count} data bytes, but ran out of arguments."
                try:
                    data_bytes = [parse_int(b) for b in action_args[idx+1 : idx+1+count]]
                except ValueError as e:
                    return f"Error parsing data byte sequence: {e}"
                actions_queue.append({'mode': 'w', 'count': count, 'data': data_bytes})
                idx += 1 + count
            else:
                actions_queue.append({'mode': 'r', 'count': count})
                idx += 1

        i2c = I2cController()
        out_stream = io.StringIO()
        try:
            i2c.configure(url, frequency=100e3)
            gpio = i2c.get_gpio()
            gpio.set_direction(mask, mask)
            gpio.write(val)
            time.sleep(0.02)  # Mux settling window

            port = i2c.get_port(target_addr)
            for action in actions_queue:
                if action['mode'] == 'w':
                    port.write(action['data'])
                elif action['mode'] == 'r':
                    rx_data = port.read(action['count'])
                    hex_output = " ".join(f"0x{b:02X}" for b in rx_data)
                    out_stream.write(hex_output + "\n")

        except I2cNackError:
            return f"Error: I2C Device at address {hex(target_addr)} NACK'd transaction."
        except Exception as e:
            return f"Execution Fault encountered: {e}"
        finally:
            i2c.terminate()
        return out_stream.getvalue().strip()


# agent factory
_agent = None

def _get_agent():
    global _agent
    if _agent is None:
        _agent = FtdiMpsseAgent()
    return _agent

def handle_dump_eeprom(url):
    return _get_agent().dump_eeprom(url)

def handle_i2cdetect(url, mask, val):
    return _get_agent().i2cdetect(url, mask, val)

def handle_i2ctransfer(url, mask, val, args):
    return _get_agent().i2ctransfer(url, mask, val, args)


methods = {
    'dump_eeprom': handle_dump_eeprom,
    'i2cdetect': handle_i2cdetect,
    'i2ctransfer': handle_i2ctransfer,
}
