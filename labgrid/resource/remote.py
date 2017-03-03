import attr

from ..factory import target_factory
from .common import Resource, NetworkResource, ManagedResource, ResourceManager


@attr.s
class RemoteManager(ResourceManager):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.url = None
        self.realm = None
        self.loop = None
        self.session = None
        self.ready = None

    def _start(self):
        if self.session:
            return

        import asyncio
        import txaio
        txaio.use_asyncio()
        txaio.config.loop = self.loop = asyncio.get_event_loop()

        from autobahn.wamp import protocol
        from autobahn.wamp.types import ComponentConfig
        from autobahn.websocket.util import parse_url
        from autobahn.asyncio.websocket import WampWebSocketClientFactory

        from ..remote.client import ClientSession

        @asyncio.coroutine
        def _connected(session):
            self.ready.set()

        def create():
            cfg = ComponentConfig(self.realm, {
                'loop': self.loop,
                'func': _connected,
            })
            self.session = ClientSession(cfg)
            return self.session

        transport_factory = WampWebSocketClientFactory(create, url=self.url)
        _, host, port, _, _, _ = parse_url(self.url)

        self.ready = asyncio.Event()
        coro = self.loop.create_connection(transport_factory, host, port)
        (transport, protocol) = self.loop.run_until_complete(coro)
        print(transport, protocol)
        self.loop.run_until_complete(self.ready.wait())

    def on_resource_added(self, resource):
        config = resource.target.env.config
        self.url = config.get_option('crossbar_url', "ws://127.0.0.1:20408/ws")
        self.realm = config.get_option('crossbar_realm', "realm1")
        self._start()
        place = self.session.get_place(resource.name)
        print(place)
        config = self.session.get_target_config(place)
        for name, args in config['resources'].items():
            new = target_factory.make_resource(resource.target, name, args)
            print("new resource {}".format(new))
        print("target {}".format(resource.target.resources))
        resource.avail=True

    def poll(self):
        import asyncio
        self.loop.run_until_complete(asyncio.sleep(0.1))
        # TODO track and update individual resources


@target_factory.reg_resource
@attr.s
class RemotePlace(ManagedResource):
    manager_cls = RemoteManager

    name = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class RemoteUSBResource(NetworkResource):
    busnum = attr.ib(validator=attr.validators.instance_of(int))
    devnum = attr.ib(validator=attr.validators.instance_of(int))
    path = attr.ib(validator=attr.validators.instance_of(str))
    vendor_id = attr.ib(validator=attr.validators.instance_of(int))
    model_id = attr.ib(validator=attr.validators.instance_of(int))


@target_factory.reg_resource
@attr.s
class NetworkAndroidFastboot(RemoteUSBResource):
    pass


@target_factory.reg_resource
@attr.s
class NetworkIMXUSBLoader(RemoteUSBResource):
    pass


@target_factory.reg_resource
@attr.s
class NetworkMXSUSBLoader(RemoteUSBResource):
    pass
