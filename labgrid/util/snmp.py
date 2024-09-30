import asyncio

import pysnmp.hlapi.v3arch.asyncio as hlapi
from ..driver.exception import ExecutionError


class SimpleSNMP:
    """A class that helps wrap pysnmp"""
    def __init__(self, host, community, port=161):
        if port is None:
            port = 161

        self.loop_created = False

        try:
            # if called from async code, try to get current's thread loop
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop_created = True
            # no previous, external or running loop found, create a new one
            self.loop = asyncio.new_event_loop()

        self.engine = hlapi.SnmpEngine()
        self.transport = self.loop.run_until_complete(hlapi.UdpTransportTarget.create((host, port)))
        self.community = hlapi.CommunityData(community, mpModel=0)
        self.context = hlapi.ContextData()

    def get(self, oid):
        g = self.loop.run_until_complete(hlapi.getCmd(self.engine, self.community, self.transport,
            self.context, hlapi.ObjectType(hlapi.ObjectIdentity(oid)),
            lookupMib=False))

        error_indication, error_status, _, res = g
        if error_indication or error_status:
            raise ExecutionError("Failed to get SNMP value.")
        return res[0][1]

    def set(self, oid, value):
        identify = hlapi.ObjectType(hlapi.ObjectIdentity(oid),
                   hlapi.Integer(value))
        g = self.loop.run_until_complete(hlapi.setCmd(self.engine, self.community, self.transport,
            self.context, identify, lookupMib=False))

        error_indication, error_status, _, _ = g
        if error_indication or error_status:
            raise ExecutionError("Failed to set SNMP value.")

    def cleanup(self):
        self.engine.closeDispatcher()
        if self.loop_created:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
