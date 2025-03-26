import sys
import socket
import threading
from time import monotonic, sleep

import gi

gi.require_version("NM", "1.0")
from gi.repository import GLib, NM

# ensure all wrapper objects for Settings types are created
for _name in dir(NM):
    if _name.startswith("Setting"):
        getattr(NM, _name)


class Future:
    def __init__(self):
        self._event = threading.Event()
        self._result = None

    def set(self, result):
        assert self._result is None
        self._result = result
        self._event.set()

    def wait(self):
        self._event.wait()
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class BackgroundLoop(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)

    def run(self):
        try:
            GLib.MainLoop(None).run()
        except Exception:
            import traceback

            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

    def block_on(self, func, *args, **kwargs):
        done = threading.Event()
        result = [None]

        def cb(data):
            result[0] = func(*args, **kwargs)
            done.set()

        GLib.main_context_default().invoke_full(GLib.PRIORITY_DEFAULT, cb, None)
        done.wait()
        return result[0]


def address_from_str(s):
    assert "/" in s, "IP address must be in the form address/prefix"
    (addr, prefix) = s.split("/", 1)
    return NM.IPAddress.new(socket.AF_INET6 if ":" in addr else socket.AF_INET, addr, int(prefix))


def connection_from_dict(data):
    con = NM.SimpleConnection.new()
    for setting_name, setting_data in data.items():
        typ = NM.Setting.lookup_type(setting_name).pytype
        setting = typ()
        for k, v in setting_data.items():
            if not v:
                continue

            if k == "mac-address":
                v = ":".join(f"{x:02X}" for x in v)
            elif k == "ssid":
                if isinstance(v, str):
                    v = v.encode()
                v = GLib.Bytes(v)
            elif k == "addresses":
                # setting addresses via the property doesn't seem to work
                for x in v:
                    setting.add_address(address_from_str(x))
                v = None

            if not v:
                continue
            try:
                setting.set_property(k, v)
            except TypeError as e:
                raise TypeError(f"Failed to set propery {k}") from e
        con.add_setting(setting)
    return con


class NMDev:
    def __init__(self, interface):
        self._interface = interface
        self._nm_dev = nm.get_device_by_iface(interface)  # pylint: disable=possibly-used-before-assignment
        if self._nm_dev is None:
            raise ValueError(f"No device found for interface {interface}")

    def _delete_connection(self, con):
        future = Future()

        def cb(con, res, error):
            assert error is None
            try:
                res = con.delete_finish(res)
                future.set(res)
            except Exception as e:
                future.set(e)

        con.delete_async(
            None,  # cancellable
            cb,
            None,
        )

    def get_settings(self):
        lg_con = nm.get_connection_by_id(f"labgrid-{self._interface}")  # pylint: disable=possibly-used-before-assignment
        if lg_con:
            return dict(lg_con.to_dbus(NM.ConnectionSerializationFlags.ALL))

    def get_active_settings(self):
        active_con = self._nm_dev.get_active_connection()
        if active_con:
            con = active_con.get_connection()
            return dict(con.to_dbus(NM.ConnectionSerializationFlags.ALL))

    def configure(self, data):
        lg_con = nm.get_connection_by_id(f"labgrid-{self._interface}")  # pylint: disable=possibly-used-before-assignment
        if lg_con:
            self._delete_connection(lg_con)
        data["connection"].update(
            {
                "id": f"labgrid-{self._interface}",
                "autoconnect": False,
                "interface-name": self._interface,
            }
        )
        con = connection_from_dict(data)

        future = Future()

        def cb(dev, res, error):
            assert error is None
            try:
                res = nm.add_and_activate_connection_finish(res)  # pylint: disable=possibly-used-before-assignment
                future.set(res)
            except Exception as e:
                future.set(e)

        nm.add_and_activate_connection_async(  # pylint: disable=possibly-used-before-assignment
            con,
            self._nm_dev,
            None,  # specific_object
            None,  # cancellable
            cb,
            None,
        )

        future.wait()  # we must wait, but don't need to return it here

    def wait_state(self, expected, timeout):
        res, out_value, _ = NM.utils_enum_from_str(NM.DeviceState, expected)
        if not res:
            raise ValueError(f"invalid state '{expected}'")
        expected = NM.DeviceState(out_value)

        timeout = monotonic() + timeout
        while monotonic() < timeout:
            sleep(0.25)
            if self._nm_dev.get_state() == expected:
                break
        else:
            raise TimeoutError(
                f"state is '{self._nm_dev.get_state().value_nick}' instead of '{expected.value_nick}'"  # pylint: disable=line-too-long
            )

    def disable(self):
        lg_con = nm.get_connection_by_id(f"labgrid-{self._interface}")  # pylint: disable=possibly-used-before-assignment
        if lg_con:
            self._delete_connection(lg_con)

    def _flags_to_str(self, flags):
        return NM.utils_enum_to_str(type(flags), flags)

    def _accesspoint_to_dict(self, ap):
        res = {}

        res["flags"] = self._flags_to_str(ap.get_flags())
        res["wpa-flags"] = self._flags_to_str(ap.get_wpa_flags())
        res["rsn-flags"] = self._flags_to_str(ap.get_rsn_flags())
        res["bssid"] = ap.get_bssid()
        if ap.get_ssid():
            res["ssid"] = ap.get_ssid().get_data().decode(errors="surrogateescape")
        res["frequency"] = ap.get_frequency()
        res["mode"] = self._flags_to_str(ap.get_mode())
        res["max-bitrate"] = ap.get_max_bitrate()
        res["strength"] = ap.get_strength()

        return res

    def get_state(self):
        state = {}

        device = {}
        device["capabilities"] = self._flags_to_str(self._nm_dev.get_capabilities())
        device["device-type"] = self._flags_to_str(self._nm_dev.get_device_type())
        device["state"] = self._flags_to_str(self._nm_dev.get_state())
        device["state-reason"] = self._flags_to_str(self._nm_dev.get_state_reason())
        device["hw-address"] = self._nm_dev.get_hw_address()
        device["driver"] = self._nm_dev.get_driver()
        device["udi"] = self._nm_dev.get_udi()
        device["mtu"] = self._nm_dev.get_mtu()
        device["vendor"] = self._nm_dev.get_vendor()
        device["product"] = self._nm_dev.get_product()
        state["device"] = device

        for name, ip_cfg in (
            ("ip4-config", self._nm_dev.get_ip4_config()),
            ("ip6-config", self._nm_dev.get_ip6_config()),
        ):
            if ip_cfg is None:
                continue
            cfg = {}
            cfg["addresses"] = []
            for address in ip_cfg.get_addresses():
                cfg["addresses"].append(f"{address.get_address()}/{address.get_prefix()}")
            cfg["gateway"] = ip_cfg.get_gateway()
            state[name] = cfg

        try:
            ap = self._nm_dev.get_active_access_point()
        except AttributeError:
            ap = None
        if ap:
            state["active-access-point"] = self._accesspoint_to_dict(ap)

        return state

    def request_scan(self):
        future = Future()

        def cb(dev, res, error):
            assert error is None
            try:
                res = dev.request_scan_finish(res)
                future.set(res)
            except Exception as e:
                future.set(e)

        self._nm_dev.request_scan_async(
            None,  # cancellable
            cb,
            None,
        )

        future.wait()  # we must wait, but don't need to return it here

    def get_access_points(self, scan):
        if scan is None:  # automatically scan if needed
            age = NM.utils_get_timestamp_msec() - self._nm_dev.get_last_scan()
            scan = bool(age > 30_000)

        if scan:
            timeout = monotonic() + 60
            last = self._nm_dev.get_last_scan()
            self.request_scan()

            while monotonic() < timeout:
                sleep(0.25)
                if self._nm_dev.get_last_scan() > last:
                    break
            else:
                raise TimeoutError("scan did not complete")

        aps = self._nm_dev.get_access_points()
        return [self._accesspoint_to_dict(ap) for ap in aps]

    def get_dhcpd_leases(self):
        leases = []
        with open(f"/var/lib/NetworkManager/dnsmasq-{self._interface}.leases") as f:
            for line in f:
                line = line.strip().split()
                if line[3] == "*":
                    line[3] = None
                if line[4] == "*":
                    line[4] = None
                leases.append(
                    {
                        "expire": int(line[0]),
                        "mac": line[1],
                        "ip": line[2],
                        "hostname": line[3],
                        "id": line[4],
                    }
                )
        return leases


if getattr(NM.Client, "__gtype__", None):
    # hide this from sphinx autodoc
    bl = BackgroundLoop()
    bl.start()
    nm = bl.block_on(NM.Client.new, None)

_nmdevs = {}


def _get_nmdev(interface):
    if interface not in _nmdevs:
        _nmdevs[interface] = NMDev(interface)
    return _nmdevs[interface]


def handle_configure(interface, settings):
    nmdev = _get_nmdev(interface)
    return nmdev.configure(settings)


def handle_wait_state(interface, expected, timeout=60):
    nmdev = _get_nmdev(interface)
    return nmdev.wait_state(expected, timeout)


def handle_disable(interface):
    nmdev = _get_nmdev(interface)
    return nmdev.disable()


def handle_get_active_settings(interface):
    nmdev = _get_nmdev(interface)
    return nmdev.get_active_settings()


def handle_get_settings(interface):
    nmdev = _get_nmdev(interface)
    return nmdev.get_settings()


def handle_get_state(interface):
    nmdev = _get_nmdev(interface)
    return nmdev.get_state()


def handle_get_dhcpd_leases(interface):
    nmdev = _get_nmdev(interface)
    return nmdev.get_dhcpd_leases()


def handle_request_scan(interface):
    nmdev = _get_nmdev(interface)
    return nmdev.request_scan()


def handle_get_access_points(interface, scan=None):
    nmdev = _get_nmdev(interface)
    return nmdev.get_access_points(scan)


methods = {
    # basic
    "configure": handle_configure,
    "wait_state": handle_wait_state,
    "disable": handle_disable,
    "get_active_settings": handle_get_active_settings,
    "get_settings": handle_get_settings,
    "get_state": handle_get_state,
    # dhcpd
    "get_dhcpd_leases": handle_get_dhcpd_leases,
    # wireless
    "request_scan": handle_request_scan,
    "get_access_points": handle_get_access_points,
}
