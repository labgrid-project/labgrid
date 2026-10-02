"""
Sentry PDU driver with sequential OID mapping for single-bank models.

This driver was tested on CW-16V1 but should work on all devices
implementing Sentry3-MIB with sequential OID numbering.

This driver uses sequential OID mapping with 16 outlets numbered
1.1.1 through 1.1.16. For multi-bank models like CW-24VDD or
4805-XLS-16, use 'sentry' instead.
"""

from ..exception import ExecutionError
from ...util.helper import processwrapper

INDEX_TO_OID = {
    1: "1.1.1", 2: "1.1.2", 3: "1.1.3", 4: "1.1.4",
    5: "1.1.5", 6: "1.1.6", 7: "1.1.7", 8: "1.1.8",
    9: "1.1.9", 10: "1.1.10", 11: "1.1.11", 12: "1.1.12",
    13: "1.1.13", 14: "1.1.14", 15: "1.1.15", 16: "1.1.16",
}

BASE_STATUS_OID = ".1.3.6.1.4.1.1718.3.2.3.1.10"
BASE_CTRL_OID = ".1.3.6.1.4.1.1718.3.2.3.1.11"

def _snmp_get(host, oid):
    out = processwrapper.check_output(
        f"snmpget -v1 -c private -O qn {host} {oid}".split()
    ).decode('ascii')
    out_oid, value = out.strip().split(' ', 1)
    assert oid == out_oid
    if value == "3" or value == "5":
        return True
    if value == "4":
        return False

def _snmp_set(host, oid, value):
    try:
        processwrapper.check_output(
            f"snmpset -v1 -c private {host} {oid} {value}".split()
        )
    except Exception as e:
        raise ExecutionError("failed to set SNMP value") from e

def power_set(host, port, index, value):
    assert port is None

    index = int(index)
    value = 1 if value else 2
    assert 1 <= index <= 16

    _snmp_set(host, f"{BASE_CTRL_OID}.{INDEX_TO_OID[index]}", f"int {value}")


def power_get(host, port, index):
    assert port is None

    index = int(index)
    assert 1 <= index <= 16

    return _snmp_get(host, f"{BASE_STATUS_OID}.{INDEX_TO_OID[index]}")
