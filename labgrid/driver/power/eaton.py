from pysnmp import hlapi
from ..exception import ExecutionError


OID = ".1.3.6.1.4.1.534.6.6.7.6.6.1"
NUMBER_OF_OUTLETS = 16


class _Snmp:
    """A class that helps wrap pysnmp"""
    def __init__(self, host, community, port=161):
        if port is None:
            port = 161

        self.engine = hlapi.SnmpEngine()
        self.transport = hlapi.UdpTransportTarget((host, port))
        self.community = hlapi.CommunityData(community, mpModel=0)
        self.context = hlapi.ContextData()

    def get(self, oid):
        g = hlapi.getCmd(self.engine, self.community, self.transport,
            self.context, hlapi.ObjectType(hlapi.ObjectIdentity(oid)),
            lookupMib=False)

        error_indication, error_status, _, res = next(g)
        if error_indication or error_status:
            raise ExecutionError("Failed to get SNMP value")
        return res[0][1]

    def set(self, oid, value):
        identify = hlapi.ObjectType(hlapi.ObjectIdentity(oid),
                   hlapi.Integer(value))
        g = hlapi.setCmd(self.engine, self.community, self.transport,
            self.context, identify, lookupMib=False)
        next(g)


def power_set(host, port, index, value):
    assert 1 <= int(index) <= NUMBER_OF_OUTLETS

    _snmp = _Snmp(host, 'public', port=port)
    cmd_id = 4 if int(value) else 3
    outlet_control_oid = "{}.{}.0.{}".format(OID, cmd_id, index)

    _snmp.set(outlet_control_oid, 1)


def power_get(host, port, index):
    assert 1 <= int(index) <= NUMBER_OF_OUTLETS

    _snmp = _Snmp(host, 'public', port=port)
    output_status_oid = "{}.2.0.{}".format(OID, index)

    value = _snmp.get(output_status_oid)

    if value == 1:  # On
        return True
    if value == 0:  # Off
        return False

    if value == 3:  # Pending on - treat as on
        return True
    if value == 2:  # Pending off - treat as off
        return False

    raise ExecutionError("failed to get SNMP value")
