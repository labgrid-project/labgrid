""" tested with NETIO 4C, should be compatible with all NETIO 4-models """

import re
import telnetlib


def power_set(host, index, value):
    index = int(index)
    assert 1 <= index <= 4
    value = "1" if value else "0"
    tn = telnetlib.Telnet(host, 1234, 1)
    tn.read_until(b"\r\n", 0.5)
    tn.write(b"login admin admin\n")
    tn.read_until(b"250 OK\r\n", 0.5)
    tn.write("port {} {}\n".format(index, value).encode())
    tn.read_until(b"250 OK\r\n", 0.5)
    tn.write(b"quit\n")
    tn.close()


def power_get(host, index):
    index = int(index)
    assert 1 <= index <= 4
    tn = telnetlib.Telnet(host, 1234, 1)
    tn.read_until(b"\r\n", 0.5)
    tn.write(b"login admin admin\n")
    tn.read_until(b"250 OK\r\n", 0.5)
    tn.write("port {}\n".format(index).encode())
    read = tn.read_until(b"\r\n", 0.5)
    m = re.match(r".*250 (\d).*", read.decode())
    if m is None:
        raise Exception("NetIO: could not match response")
    value = m.group(1)
    tn.write(b"quit\n")
    tn.close()
    return value == "1"
