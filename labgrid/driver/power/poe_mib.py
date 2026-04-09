""" tested with Cisco CBS350, should be compatible with switches implementing the PoE administration MiB"""

from ..exception import ExecutionError
from ...util.snmp import SimpleSNMP

OID = "1.3.6.1.2.1.105.1.1.1.3.1"

def power_set(host, port, index, value):
    _snmp = SimpleSNMP(host, 'private', port=port)
    outlet_control_oid = "{}.{}".format(OID, index)

    oid_value = "1" if value else "2"

    _snmp.set(outlet_control_oid, oid_value)
    _snmp.cleanup()

def power_get(host, port, index):
    _snmp = SimpleSNMP(host, 'private', port=port)
    output_status_oid = "{}.{}".format(OID, index)

    value = _snmp.get(output_status_oid)

    _snmp.cleanup()
    if value == 1:  # On
        return True
    if value == 2:  # Off
        return False

    raise ExecutionError("failed to get SNMP value")
