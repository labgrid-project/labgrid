"""
This module implements switching GPIOs via gpio-manager D-Bus service.

Takes chip' and 'pin' as parameters which are the path to the gpiochip device
and the pin name/number respectively.

"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, Union, cast

from jeepney import DBusAddress, MessageGenerator, Properties, new_method_call
from jeepney.io.blocking import Proxy, open_dbus_connection


class PropertiesProxy(Protocol):
    def get_all(self) -> tuple[dict[str, Any]]: ...


class ObjectManagerProxy(Protocol):
    def GetManagedObjects(self) -> tuple[dict[str, dict[str, dict[str, Any]]]]: ...


class ObjectManager(MessageGenerator):
    interface = "org.freedesktop.DBus.ObjectManager"

    def __init__(self, object_path: str, bus_name: str = "io.gpiod1") -> None:
        super().__init__(object_path=object_path, bus_name=bus_name)

    def GetManagedObjects(self):
        return new_method_call(self, "GetManagedObjects")


class ChipProxy(Protocol):
    def RequestLines(
        self,
        line_config: tuple[list[tuple[list[int], dict[str, tuple[str, Any]]]], list[int]],
        request_config: dict[str, tuple[str, Any]],
    ) -> tuple[str]: ...


class Chip(MessageGenerator):
    interface = "io.gpiod1.Chip"

    def __init__(self, object_path: str, bus_name: str = "io.gpiod1"):
        super().__init__(object_path=object_path, bus_name=bus_name)

    def RequestLines(self, line_config: Any, request_config: Any):
        return new_method_call(self, "RequestLines", "(a(aua{sv})ai)a{sv}", (line_config, request_config))


class RequestProxy(Protocol):
    def Release(self) -> None: ...
    def ReconfigureLines(
        self, line_config: tuple[list[tuple[list[int], dict[str, tuple[str, Any]]]], list[int]]
    ) -> None: ...
    def GetValues(self, offsets: list[int]) -> tuple[list[int]]: ...
    def SetValues(self, values: dict[int, int]) -> None: ...


class Request(MessageGenerator):
    interface = "io.gpiod1.Request"

    def __init__(self, object_path: str, bus_name: str = "io.gpiod1") -> None:
        super().__init__(object_path=object_path, bus_name=bus_name)

    def Release(self):
        return new_method_call(self, "Release")

    def ReconfigureLines(self, line_config: Any):
        return new_method_call(self, "ReconfigureLines", "(a(aua{sv})ai)", (line_config,))

    def GetValues(self, offsets: Any):
        return new_method_call(self, "GetValues", "au", (offsets,))

    def SetValues(self, values: Any):
        return new_method_call(self, "SetValues", "a{ui}", (values,))


class GpioDigitalOutput:
    def __init__(self, chip: str, pin: Union[str, int]) -> None:
        self._logger = logging.getLogger("Device: ")

        # If chip is int, assume it's the gpiochip number and construct the name
        # from that. Otherwise, resolve the path in case it is a symlink and
        # get the real name from that.
        chip = f"gpiochip{chip}" if isinstance(chip, int) else str(Path(chip).resolve().name)

        # Then connect to D-Bus and look for a matching request.

        self._system_bus = open_dbus_connection(bus="SYSTEM")

        requests_obj = cast(ObjectManagerProxy, Proxy(ObjectManager("/io/gpiod1/requests"), self._system_bus))
        (requests,) = requests_obj.GetManagedObjects()

        for req_path, props in requests.items():
            req = props["io.gpiod1.Request"]

            if Path(req["ChipPath"][1]).name != chip:
                continue

            for line_path in req["LinePaths"][1]:
                line_obj = cast(
                    PropertiesProxy,
                    Proxy(Properties(DBusAddress(line_path, "io.gpiod1", "io.gpiod1.Line")), self._system_bus),
                )
                (line,) = line_obj.get_all()

                if line["Offset"][1] == pin or line["Name"][1] == pin:
                    self._offset: int = line["Offset"][1]
                    self._req = cast(RequestProxy, Proxy(Request(req_path), self._system_bus))
                    break

            else:
                continue

            break

        else:
            # If we didn't find a match, the make the request ourselves.
            self._logger.debug("Requesting GPIO %r on chip %r via gpio-manager.", pin, chip)

            chips_obj = cast(ObjectManagerProxy, Proxy(ObjectManager("/io/gpiod1/chips"), self._system_bus))
            (chips,) = chips_obj.GetManagedObjects()

            for chip_path, props in chips.items():
                chip_info = props["io.gpiod1.Chip"]

                if chip_info["Name"][1] != chip:
                    continue

                if isinstance(pin, str):
                    raise NotImplementedError("Pin name lookup not implemented, only pin index.")

                chip_obj = cast(ChipProxy, Proxy(Chip(chip_path), self._system_bus))
                (req_path,) = chip_obj.RequestLines(([([pin], {})], []), {})

                self._offset = pin
                self._req = cast(RequestProxy, Proxy(Request(req_path), self._system_bus))

                break
            else:
                raise ValueError(f"Chip {chip!r} not found.")

    def __del__(self):
        if self._system_bus:
            self._system_bus.close()
            self._system_bus = None

    def get(self) -> bool:
        return bool(self._req.GetValues([self._offset])[0][0])

    def set(self, status: bool) -> None:
        # Have to call ReconfigureLines instead of SetValue in case the line is
        # currently configured as input (SetValue fails rather than changing the direction).
        self._req.ReconfigureLines(([([self._offset], {"direction": ("s", "output")})], [status]))


_gpios: dict[tuple[str, Union[str, int]], GpioDigitalOutput] = {}


def _get_gpio_line(chip: str, pin: Union[str, int]) -> GpioDigitalOutput:
    real_chip = str(Path(chip).resolve())

    if (real_chip, pin) not in _gpios:
        _gpios[(real_chip, pin)] = GpioDigitalOutput(real_chip, pin)

    return _gpios[(real_chip, pin)]


def handle_set(chip: str, pin: Union[str, int], status: bool) -> None:
    gpio_line = _get_gpio_line(chip, pin)
    gpio_line.set(status)


def handle_get(chip: str, pin: Union[str, int]) -> bool:
    gpio_line = _get_gpio_line(chip, pin)
    return gpio_line.get()


methods: dict[str, Callable[..., Any]] = {
    "set": handle_set,
    "get": handle_get,
}
