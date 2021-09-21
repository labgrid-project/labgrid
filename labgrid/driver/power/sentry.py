"""
This driver was tested on those models: CW-24VDD and 4805-XLS-16
but should be working on all devices implementing Sentry3-MIB
"""

from ..exception import ExecutionError
from ...util.helper import processwrapper

INDEX_TO_OID = {
    1: "1.1.1",
    2: "1.1.2",
    3: "1.1.3",
    4: "1.1.4",
    5: "1.1.5",
    6: "1.1.6",
    7: "1.1.7",
    8: "1.1.8",
    9: "1.2.1",
    10: "1.2.2",
    11: "1.2.3",
    12: "1.2.4",
    13: "1.2.5",
    14: "1.2.6",
    15: "1.2.7",
    16: "1.2.8",
    17: "1.3.1",
    18: "1.3.2",
    19: "1.3.3",
    20: "1.3.4",
    21: "1.3.5",
    22: "1.3.6",
    23: "1.3.7",
    24: "1.3.8",
    25: "1.4.1",
    26: "1.4.2",
    27: "1.4.3",
    28: "1.4.4",
    29: "1.4.5",
    30: "1.4.6",
    31: "1.4.7",
    32: "1.4.8",
    33: "1.5.1",
    34: "1.5.2",
    35: "1.5.3",
    36: "1.5.4",
    37: "1.5.5",
    38: "1.5.6",
    39: "1.5.7",
    40: "1.5.8",
    41: "1.6.1",
    42: "1.6.2",
    43: "1.6.3",
    44: "1.6.4",
    45: "1.6.5",
    46: "1.6.6",
    47: "1.6.7",
    48: "1.6.8",
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
    assert 1 <= index <= 48

    _snmp_set(host, f"{BASE_CTRL_OID}.{INDEX_TO_OID[index]}", f"int {value}")


def power_get(host, port, index):
    assert port is None

    index = int(index)
    assert 1 <= index <= 48

    return _snmp_get(host, f"{BASE_STATUS_OID}.{INDEX_TO_OID[index]}")
