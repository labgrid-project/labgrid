import logging
from pprint import pprint

from labgrid import Environment
from labgrid.logging import basicConfig, StepLogger


# enable debug logging
basicConfig(level=logging.DEBUG)

# show labgrid steps on the console
StepLogger.start()


e = Environment("nm.env")
t = e.get_target()
d = t.get_driver("NetworkInterfaceDriver")

# based on https://developer.gnome.org/NetworkManager/stable/ch01.html, but adapted to python dicts
s_client = {
    "connection": {
        "type": "802-11-wireless",
    },
    "802-11-wireless": {
        "mode": "infrastructure",
        "ssid": "local-rpi",
    },
    "802-11-wireless-security": {
        "key-mgmt": "wpa-psk",
        "psk": "obMinwyurArc5",
    },
    "ipv4": {
        "method": "auto",
        "ignore-auto-dns": True,
        "ignore-auto-routes": True,
        "never-default": True,
    },
    "ipv6": {
        "method": "link-local",
    },
}
s_ap = {
    "connection": {
        "type": "802-11-wireless",
    },
    "802-11-wireless": {
        "mode": "ap",
        "ssid": "local-rpi",
    },
    "802-11-wireless-security": {
        "key-mgmt": "wpa-psk",
        "psk": "obMinwyurArc5",
    },
    "ipv4": {
        #'method': "auto",
        #'method': "link-local",
        "method": "shared",
        "addresses": ["172.16.0.2/29"],
    },
    "ipv6": {
        "method": "link-local",
    },
}

d.disable()
d.wait_state("disconnected")
print("access points after scan")
pprint(d.get_access_points())

d.configure(s_ap)
d.wait_state("activated")
print("settings in AP mode")
pprint(d.get_settings())
print("state in AP mode")
pprint(d.get_state())

# d.configure(s_client)
# d.wait_state('activated')
# print("settings in client mode")
# pprint(d.get_settings())
# print("state in client mode")
# pprint(d.get_state())
