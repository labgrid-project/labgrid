from ..exception import ExecutionError
from ...util.helper import processwrapper

OID = ".1.3.6.1.4.1.318.1.1.4.4.2.1.3"

def _snmp_get(host, oid):
    out = processwrapper.check_output(
        f"snmpget -v1 -c private -O qn {host} {oid}".split()
    ).decode('ascii')
    out_oid, value = out.strip().split(' ', 1)
    assert oid == out_oid
    if value == "1":
        return True
    if value == "2":
        return False

    raise ExecutionError("failed to get SNMP value")


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
    assert 1 <= index <= 8

    _snmp_set(host, f"{OID}.{index}", f"int {value}")


def power_get(host, port, index):
    assert port is None

    index = int(index)
    assert 1 <= index <= 8

    return _snmp_get(host, f"{OID}.{index}")
