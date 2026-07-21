from ..exception import ExecutionError
from ...util.snmp import SimpleSNMP


OID = ".1.3.6.1.4.1.534.6.6.7.6.6.1"
NUMBER_OF_OUTLETS = 16


def power_set(host, port, index, value):
    assert 1 <= int(index) <= NUMBER_OF_OUTLETS

    _snmp = SimpleSNMP(host, 'public', port=port)
    cmd_id = 4 if int(value) else 3
    outlet_control_oid = "{}.{}.0.{}".format(OID, cmd_id, index)

    _snmp.set(outlet_control_oid, 1)
    _snmp.cleanup()


def power_get(host, port, index):
    assert 1 <= int(index) <= NUMBER_OF_OUTLETS

    _snmp = SimpleSNMP(host, 'public', port=port)
    output_status_oid = "{}.2.0.{}".format(OID, index)

    value = _snmp.get(output_status_oid)

    _snmp.cleanup()
    if value == 1:  # On
        return True
    if value == 0:  # Off
        return False

    if value == 3:  # Pending on - treat as on
        return True
    if value == 2:  # Pending off - treat as off
        return False

    raise ExecutionError("failed to get SNMP value")
