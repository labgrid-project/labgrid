'''
This Driver was tested on a FL SWITCH 2303-8SP1 with FW-version 3.27.01 BETA
file   phoenix_fl_switch.py
author Raffael Krakau
date   2023-08-24

Copyright 2023 JUMO GmbH & Co. KG
'''
import pexpect

PORT = 23


def __login_telnet(tn):
    """
    Login user with set credentials

    @param tn : pyexpect-telnet-object
    """
    username = "admin"
    password = "private"

    # login user with password
    tn.expect(b'User: ')
    tn.send(bytes(f'{username}\r\n', "utf-8"))
    tn.expect(b'Password: ')
    tn.send(bytes(f'{password}\r\n', "utf-8"))


def power_set(host, port, index: int, value: bool):
    """
    Set power state by socket port number (e.g. 1 - 8) and an value {'enable', 'disable'}.

    - values:
        - disable(False): Turn OFF,
        - enable(True): Turn ON
    """
    action = "enable" if value else "disable"

    with pexpect.spawn(f"telnet {host} {port}", timeout=1) as tn:
        # login user with password
        __login_telnet(tn)

        # set value
        tn.send(bytes(f'pse port {index} power {action}\r\n', 'utf-8'))

        tn.expect(b'OK')

        tn.send(b"quit\r\n")
        tn.expect(pexpect.EOF)


def power_get(host, port, index: int) -> bool:
    """
    Get current state of a given socket number.
    - host: spe-switch-device adress
    - port: standard is 23
    - index: depends on spe-switch-device 1-n (n is the number of spe-switch-ports)
    """
    status = None

    with pexpect.spawn(f"telnet {host} {port}", timeout=1) as tn:
        # login user with password
        __login_telnet(tn)

        # get value
        tn.send(bytes(f'show pse port port-no {index}\r\n', "utf-8"))

        status = tn.expect(['disable', 'enable'])

        tn.send(b"quit\r\n")
        tn.expect(pexpect.EOF)

    return True if status == 1 else False
