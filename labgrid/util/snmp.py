from pysnmp import hlapi
from ..driver.exception import ExecutionError


class SimpleSNMP:
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
            raise ExecutionError("Failed to get SNMP value.")
        return res[0][1]

    def set(self, oid, value):
        identify = hlapi.ObjectType(hlapi.ObjectIdentity(oid),
                   hlapi.Integer(value))
        g = hlapi.setCmd(self.engine, self.community, self.transport,
            self.context, identify, lookupMib=False)
        next(g)
