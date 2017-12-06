import logging
import subprocess
import attr
from time import time

from ..factory import target_factory
from .common import Resource, ManagedResource, ResourceManager

@attr.s
class SNMPSwitch:
    """SNMPSwitch describes a switch accessible over SNMP. This class
    implements functions to query ports and the forwarding database."""
    hostname = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.logger = logging.getLogger("{}".format(self))
        self.ports = {}
        self.fdb = {}
        self.macs_by_port = {}
        self._autodetect()

    def _autodetect(self):
        from pysnmp import hlapi

        for (errorIndication, errorStatus, errorIndex, varBindTable) in hlapi.getCmd(
                hlapi.SnmpEngine(),
                hlapi.CommunityData('public'),
                hlapi.UdpTransportTarget((self.hostname, 161)),
                hlapi.ContextData(),
                hlapi.ObjectType(hlapi.ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0))):
            if errorIndication:
                Exception("snmp error {}".format(errorIndication))
            elif errorStatus:
                Exception("snmp error {}".format(errorStatus))
            else:
                sysDescr = str(varBindTable[0][1])

        if sysDescr.startswith("HPE OfficeConnect Switch 1820 24G J9980A,"):
            self._get_fdb = self._get_fdb_dot1q
        elif sysDescr.startswith("HP 1810-24G,"):
            self._get_fdb = self._get_fdb_dot1d
        else:
            Exception("unsupported switch {}".format(sysDescr))

        self.logger.debug("autodetected switch{}: {} {}".format(
            sysDescr, self._get_ports, self._get_fdb))

    def _get_ports(self):
        """Fetch ports and their values via SNMP

        Returns:
            Dict[Dict[]]: ports and their values
        """
        from pysnmp import hlapi

        vars = [
            (hlapi.ObjectType(hlapi.ObjectIdentity('IF-MIB', 'ifIndex')),'index'),
            (hlapi.ObjectType(hlapi.ObjectIdentity('IF-MIB', 'ifDescr')), 'descr'),
            (hlapi.ObjectType(hlapi.ObjectIdentity('IF-MIB', 'ifSpeed')), 'speed'),
            (hlapi.ObjectType(hlapi.ObjectIdentity('IF-MIB', 'ifOperStatus')), 'status'),
            (hlapi.ObjectType(hlapi.ObjectIdentity('IF-MIB', 'ifInErrors')), 'inErrors'),
            (hlapi.ObjectType(hlapi.ObjectIdentity('IF-MIB', 'ifHCInOctets')), 'inOctets'),
            (hlapi.ObjectType(hlapi.ObjectIdentity('IF-MIB', 'ifHCOutOctets')), 'outOctets'),
        ]
        ports = {}

        for (errorIndication, errorStatus, errorIndex, varBindTable) in hlapi.bulkCmd(
                hlapi.SnmpEngine(),
                hlapi.CommunityData('public'),
                hlapi.UdpTransportTarget((self.hostname, 161)),
                hlapi.ContextData(),
                0, 20,
                *[x[0] for x in vars],
                lexicographicMode=False):
            if errorIndication:
                Exception("snmp error {}".format(errorIndication))
            elif errorStatus:
                Exception("snmp error {}".format(errorStatus))
            else:
                port = {}
                for (key, val), (base, label) in zip(varBindTable, vars):
                    index = key.getMibSymbol()[-1][0].prettyPrint()
                    val = val.prettyPrint()
                    if label == 'status':
                        val = val.strip("'")
                    port[label] = val
                ports[port.pop('index')] = port

        return ports

    def _get_fdb_dot1d(self):
        """Fetch the forwarding database via SNMP using the BRIDGE-MIB

        Returns:
            Dict[List[str]]: ports and their values
        """
        from pysnmp import hlapi

        ports = {}

        for (errorIndication, errorStatus, errorIndex, varBindTable) in hlapi.bulkCmd(
                hlapi.SnmpEngine(),
                hlapi.CommunityData('public'),
                hlapi.UdpTransportTarget((self.hostname, 161)),
                hlapi.ContextData(),
                0, 50,
                hlapi.ObjectType(hlapi.ObjectIdentity('BRIDGE-MIB', 'dot1dTpFdbPort')),
                lexicographicMode=False):
            if errorIndication:
                Exception("snmp error {}".format(errorIndication))
            elif errorStatus:
                Exception("snmp error {}".format(errorStatus))
            else:
                for varBinds in varBindTable:
                    key, val = varBinds
                    if not val:
                        continue
                    mac = key.getMibSymbol()[-1][0].prettyPrint()
                    interface = str(int(val))
                    ports.setdefault(interface, []).append(mac)

        return ports

    def _get_fdb_dot1q(self):
        """Fetch the forwarding database via SNMP using the Q-BRIDGE-MIB

        Returns:
            Dict[List[str]]: ports and their values
        """
        from pysnmp import hlapi

        ports = {}

        for (errorIndication, errorStatus, errorIndex, varBindTable) in hlapi.bulkCmd(
                hlapi.SnmpEngine(),
                hlapi.CommunityData('public'),
                hlapi.UdpTransportTarget((self.hostname, 161)),
                hlapi.ContextData(),
                0, 50,
                hlapi.ObjectType(hlapi.ObjectIdentity('Q-BRIDGE-MIB', 'dot1qTpFdbPort')),
                lexicographicMode=False):
            if errorIndication:
                Exception("snmp error {}".format(errorIndication))
            elif errorStatus:
                Exception("snmp error {}".format(errorStatus))
            else:
                for varBinds in varBindTable:
                    key, val = varBinds
                    if not val:
                        continue
                    mac = key.getMibSymbol()[-1][1].prettyPrint()
                    interface = str(int(val))
                    ports.setdefault(interface, []).append(mac)

        return ports

    def _update_macs(self):
        """remember the first time we've seen a MAC on a port"""
        for removed in self.macs_by_port.keys() - self.ports.keys():
            del self.macs_by_port[removed]
        for interface, macs in self.fdb.items():
            seen = self.macs_by_port.setdefault(interface, {})
            for removed in seen.keys() - set(macs):
                del seen[removed]
            for mac in macs:
                seen.setdefault(mac, int(time()))

    def update(self):
        """Update port status and forwarding database status

        Returns:
            None
        """
        self.logger.debug("polling switch FDB")
        self.fdb = self._get_fdb()
        self.logger.debug("polling switch ports")
        self.ports = self._get_ports()
        self.logger.debug("updating macs by port")
        self._update_macs()


@attr.s
class EthernetPortManager(ResourceManager):
    """The EthernetPortManager periodically polls the switch for new updates."""
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}".format(self))
        self.loop = None
        self.poll_tasks = []
        self.switches = {}
        self.neighbors = {}

    def on_resource_added(self, resource):
        """Handler to execute when the resource is added

        Checks whether the resource can be managed by this Manager and starts
        the event loop.

        Args:
            resource(Resource): resource to check against

        Returns:
            None
        """
        if not isinstance(resource, SNMPEthernetPort):
            return
        self._start()
        resource.avail=True

    def _start(self):
        """Internal function to register as task and attach/start the event
        loop

        Returns:
            None
        """
        import asyncio

        if self.poll_tasks:
            return

        @asyncio.coroutine
        def poll_neighbour(self):
            self.logger.debug("polling neighbor table")
            self.neighbors = self._get_neigh()

            yield from asyncio.sleep(1.0)

        @asyncio.coroutine
        def poll_switches(self):
            current = set(resource.switch for resource in self.resources)
            removed = set(self.switches) - current
            new = current - set(self.switches)
            for switch in removed:
                del self.switches[switch]
            for switch in new:
                self.switches[switch] = SNMPSwitch(switch)
            for switch in current:
                self.switches[switch].update()
                yield from asyncio.sleep(1.0)

            yield from asyncio.sleep(2.0)

        @asyncio.coroutine
        def poll(self, handler):
            while True:
                try:
                    yield from asyncio.sleep(1.0)
                    yield from handler(self)
                except asyncio.CancelledError:
                    break
                except:
                    import traceback
                    traceback.print_exc()

        self.loop = asyncio.get_event_loop()
        self.poll_tasks.append(self.loop.create_task(poll(self, poll_neighbour)))
        self.poll_tasks.append(self.loop.create_task(poll(self, poll_switches)))

    def _get_neigh(self):
        """Internal function to retrieve the neighbors on the test machine

        Returns:
            Dict[Tuple[(str,str,str)]]: dictionary with mac addresses as keys
            and a Tuple of address, device and state as values
        """
        neighbors = {}

        for line in subprocess.check_output(['ip', 'neigh', 'show']).splitlines():
            line = line.decode('ascii').strip().split()
            addr = line.pop(0)
            if line[0] == 'dev':
                line.pop(0)
                dev = line.pop(0)
            else:
                dev = None
            if line[0] == 'lladdr':
                line.pop(0)
                lladdr = line.pop(0)
            else:
                lladdr = None
            if line[0] == 'router':
                line.pop()
            state = line.pop(0)
            assert not line
            # TODO: check if we could use the device and state information
            neighbors.setdefault(lladdr, []).append(addr)
        for value in neighbors.values():
            value.sort()

        return neighbors

    def poll(self):
        """Updates the state with new information from the event loop

        Returns:
            None
        """
        import asyncio
        if not self.loop.is_running():
            self.loop.run_until_complete(asyncio.sleep(0.0))
        for resource in self.resources:
            switch = self.switches.get(resource.switch)
            if not switch:
                resource.extra = None
                continue
            extra = {}
            for mac, timestamp in switch.macs_by_port.get(resource.interface, {}).items():
                extra.setdefault('macs', {})[mac] = {
                    'timestamp': timestamp,
                    'ips': self.neighbors.get(mac, []),
                }
            extra.update(switch.ports.get(resource.interface, {}))
            if resource.extra != extra:
                resource.extra = extra
                self.logger.debug("new information for {}: {}".format(resource, extra))


@target_factory.reg_resource
@attr.s
class SNMPEthernetPort(ManagedResource):
    """SNMPEthernetPort describes an ethernet port which can be queried over
    SNMP.

    Args:
        switch (str): hostname of the switch to query
        interface (str): name of the interface to query
    """
    manager_cls = EthernetPortManager

    switch = attr.ib(validator=attr.validators.instance_of(str))
    interface = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.extra = {}
