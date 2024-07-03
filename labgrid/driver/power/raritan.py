"""Driver for the Raritan PDUs

Documentation sources:
* https://www.circitor.fr/Mibs/Html/P/PDU2-MIB.php
* http://support.raritan.com/px3/version-3.0.3/user-guides/PX3-0B-v3.0-E.pdf
* https://cdn1.raritan.com/download/pdu-g2/4.0.20/MIB_Usage_4.0.20_49038.pdf
"""
from ..exception import ExecutionError
from ...util.snmp import SimpleSNMP


OID = ".1.3.6.1.4.1.13742.6.4.1.2.1"


def power_set(host, port, index, value):
    _snmp = SimpleSNMP(host, 'private', port=port)
    outlet_control_oid = "{}.2.1.{}".format(OID, index)

    _snmp.set(outlet_control_oid, str(int(value)))


def power_get(host, port, index):
    _snmp = SimpleSNMP(host, 'public', port=port)
    output_status_oid = "{}.3.1.{}".format(OID, index)

    value = _snmp.get(output_status_oid)

    if value == 7:  # On
        return True
    if value == 8:  # Off
        return False

    raise ExecutionError("failed to get SNMP value")
