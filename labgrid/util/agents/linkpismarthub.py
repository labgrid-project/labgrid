"""
This module implements the communication protocol to power on/off ports on a
LinkPi SmartHUB, a 12-port USB3.0 HUB utilizing four RTS5411 USB3.0 4-port HUB
controllers, a FT232R USB UART IC and a STM32F103RB MCU for port power control.

The protocol is a simple line-based protocol over a serial port.

Known commands:
- onoff <port> <1|0> - switch port power on/off
- state - get current power state of all ports
- SetOWP <1|0> <1|0> ... - set the power-on state of all ports
- GetOWP - get the power-on state of all ports

Responses are in JSON format, e.g.:

.. code-block:: text

  > onoff 5 1
  < {"Cmd":"OnOffResp","SeqNum":1,"ret":0}
  > state
  < {"Cmd":"StateResp","SeqNum":2,"state":[0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]}
  > SetOWP 0 0 0 0 0 0 0 0 0 0 0 1
  < {"Cmd":"SetOWPResp","SeqNum":3,"ret":0}
  > GetOWP
  < {"Cmd":"GetOWPResp","SeqNum":4,"owp":[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]}

A version announcement is continuously sent every second:

.. code-block:: text

  < {"Cmd":"VerResp","ver":"SmartHUB_<ver>","uid":"<uid>"}
"""
import json
import serial


PORT_INDEX_MAP = {
    "1": 5, "2": 4, "3": 3, "4": 2, "5": 1, "6": 0,
    "7": 11, "8": 10, "9": 9, "10": 8, "11": 7, "12": 6,
}


# Port names printed on the device do not match the internal port index
def name_to_index(name_or_index):
    return PORT_INDEX_MAP.get(name_or_index, name_or_index)


class LinkPiSmartHUB:
    def __init__(self, path):
        if not path:
            raise ValueError("Device not found")
        self.path = path

    def _command(self, command):
        with serial.Serial(self.path, 115200, timeout=2) as s:
            # wait on next version announcement
            s.readline()
            # send the command
            s.write(f"{command}\r\n".encode())
            # read and return the response
            return s.readline().decode().strip()

    def onoff(self, index, state):
        return self._command(f"onoff {index} {state}")

    def state(self):
        return self._command("state")


def handle_set(path, name_or_index, state):
    smarthub = LinkPiSmartHUB(path)
    smarthub.onoff(name_to_index(name_or_index), state)


def handle_get(path, name_or_index):
    smarthub = LinkPiSmartHUB(path)
    state = smarthub.state()
    return bool(json.loads(state).get("state")[name_to_index(name_or_index)])


methods = {
    "set": handle_set,
    "get": handle_get,
}
