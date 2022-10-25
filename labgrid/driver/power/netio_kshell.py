""" tested with NETIO 4C, should be compatible with all NETIO 4-models """

import re

import pexpect

PORT = 1234

def power_set(host, port, index, value):
    index = int(index)
    assert 1 <= index <= 4
    value = "1" if value else "0"

    with pexpect.spawn(f"telnet {host} {port}", timeout=1) as tn:
        tn.expect(b"100 HELLO .*\r\n")
        tn.send(b"login admin admin\r\n")

        tn.expect(b"250 OK\r\n")
        tn.send(f"port {index} {value}\r\n".encode())

        tn.expect(b"250 OK\r\n")
        tn.send(b"quit\r\n")
        tn.expect(pexpect.EOF)


def power_get(host, port, index):
    index = int(index)
    assert 1 <= index <= 4

    with pexpect.spawn(f"telnet {host} {port}", timeout=1) as tn:
        tn.expect(b"100 HELLO .*\r\n")
        tn.send(b"login admin admin\r\n")

        tn.expect(b"250 OK\r\n")
        tn.send(f"port {index}\r\n".encode())

        tn.expect(rb"250 .*\r\n")
        m = re.match(r".*250 (\d).*", tn.after.decode())
        if m is None:
            raise Exception("NetIO: could not match response")
        value = m.group(1)

        tn.send(b"quit\r\n")
        tn.expect(pexpect.EOF)

    return value == "1"
