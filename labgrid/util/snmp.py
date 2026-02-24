import pysnmp.hlapi.v3arch.asyncio as hlapi
from ..driver.exception import ExecutionError
from .loop import ensure_event_loop, is_new_loop


class SimpleSNMP:
    """A class that helps wrap pysnmp"""

    def __init__(self, host, community, port=161):
        if port is None:
            port = 161

        self.loop = ensure_event_loop()

        self.engine = hlapi.SnmpEngine()
        self.transport = self.loop.run_until_complete(hlapi.UdpTransportTarget.create((host, port)))
        self.community = hlapi.CommunityData(community, mpModel=0)
        self.context = hlapi.ContextData()

    def get(self, oid):
        g = self.loop.run_until_complete(
            hlapi.getCmd(
                self.engine,
                self.community,
                self.transport,
                self.context,
                hlapi.ObjectType(hlapi.ObjectIdentity(oid)),
                lookupMib=False,
            )
        )

        error_indication, error_status, _, res = g
        if error_indication or error_status:
            raise ExecutionError("Failed to get SNMP value.")
        return res[0][1]

    def set(self, oid, value):
        identify = hlapi.ObjectType(hlapi.ObjectIdentity(oid), hlapi.Integer(value))
        g = self.loop.run_until_complete(
            hlapi.setCmd(self.engine, self.community, self.transport, self.context, identify, lookupMib=False)
        )

        error_indication, error_status, _, _ = g
        if error_indication or error_status:
            raise ExecutionError("Failed to set SNMP value.")

    def cleanup(self):
        self.engine.closeDispatcher()
        if is_new_loop(self.loop):
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
