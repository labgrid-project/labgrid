"""The coordinator module coordinates exported resources and clients accessing them."""
# pylint: disable=no-member,unused-argument
import asyncio
import traceback
from collections import defaultdict
from os import environ
from pprint import pprint
from enum import Enum

import attr
import yaml
from autobahn import wamp
from autobahn.asyncio.wamp import ApplicationRunner, ApplicationSession
from autobahn.wamp.types import RegisterOptions

from .common import ResourceEntry, ResourceMatch, Place, enable_tcp_nodelay


class Action(Enum):
    ADD = 0
    DEL = 1
    UPD = 2


@attr.s(init=False, cmp=False)
class RemoteSession:
    """class encapsulating a session, used by ExporterSession and ClientSession"""
    coordinator = attr.ib()
    session = attr.ib()
    authid = attr.ib()
    version = attr.ib(default="unknown", init=False)

    @property
    def key(self):
        """Key of the session"""
        return self.session

    @property
    def name(self):
        """Name of the session"""
        return self.authid.split('/', 1)[1]


@attr.s(cmp=False)
class ExporterSession(RemoteSession):
    """An ExporterSession is opened for each Exporter connecting to the
    coordinator, allowing the Exporter to get and set resources"""
    groups = attr.ib(default=attr.Factory(dict), init=False)

    def set_resource(self, groupname, resourcename, resource):
        group = self.groups.setdefault(groupname, {})
        old = group.get(resourcename)
        if resource:
            new = group[resourcename] = ResourceEntry(resource)
            cls = new.cls
        elif old:
            new = None
            cls = old.cls
            del group[resourcename]
        else:
            new = None
            cls = None

        self.coordinator.publish(
            'org.labgrid.coordinator.resource_changed', self.name,
            groupname, resourcename, new.asdict() if new else {}
        )

        resource_path = (self.name, groupname, cls, resourcename)

        if old and new:
            assert old.cls == new.cls
            return Action.UPD, resource_path
        elif old:
            return Action.DEL, resource_path
        elif new:
            return Action.ADD, resource_path

        return None, resource_path

    def get_resources(self):
        """Method invoked by the exporter, get a resource from the coordinator"""
        result = {}
        for groupname, group in self.groups.items():
            result_group = result[groupname] = {}
            for resourcename, resource in group.items():
                result_group[resourcename] = resource.asdict()
        return result


@attr.s(cmp=False)
class ClientSession(RemoteSession):
    acquired = attr.ib(default=attr.Factory(list), init=False)


class CoordinatorComponent(ApplicationSession):
    async def onConnect(self):
        self.sessions = {}
        self.places = {}
        self.poll_task = None
        self.save_scheduled = False

        self.load()
        self.save_later()

        enable_tcp_nodelay(self)
        self.join(self.config.realm, ["ticket"], "coordinator")

    def onChallenge(self, challenge):
        return "dummy-ticket"

    async def onJoin(self, details):
        await self.subscribe(self.on_session_join, 'wamp.session.on_join')
        await self.subscribe(
            self.on_session_leave, 'wamp.session.on_leave'
        )
        await self.register(
            self.attach,
            'org.labgrid.coordinator.attach',
            options=RegisterOptions(details_arg='details')
        )

        # resources
        await self.register(
            self.set_resource,
            'org.labgrid.coordinator.set_resource',
            options=RegisterOptions(details_arg='details')
        )
        await self.register(
            self.get_resources,
            'org.labgrid.coordinator.get_resources'
        )

        # places
        await self.register(
            self.add_place, 'org.labgrid.coordinator.add_place'
        )
        await self.register(
            self.del_place, 'org.labgrid.coordinator.del_place'
        )
        await self.register(
            self.add_place_alias, 'org.labgrid.coordinator.add_place_alias'
        )
        await self.register(
            self.del_place_alias, 'org.labgrid.coordinator.del_place_alias'
        )
        await self.register(
            self.set_place_comment, 'org.labgrid.coordinator.set_place_comment'
        )
        await self.register(
            self.add_place_match, 'org.labgrid.coordinator.add_place_match'
        )
        await self.register(
            self.del_place_match, 'org.labgrid.coordinator.del_place_match'
        )
        await self.register(
            self.acquire_place,
            'org.labgrid.coordinator.acquire_place',
            options=RegisterOptions(details_arg='details')
        )
        await self.register(
            self.release_place,
            'org.labgrid.coordinator.release_place',
            options=RegisterOptions(details_arg='details')
        )
        await self.register(
            self.allow_place,
            'org.labgrid.coordinator.allow_place',
            options=RegisterOptions(details_arg='details')
        )
        await self.register(
            self.get_places, 'org.labgrid.coordinator.get_places'
        )

        self.poll_task = asyncio.get_event_loop().create_task(self.poll())

        print("Coordinator ready.")

    async def onLeave(self, details):
        self.save()
        if self.poll_task:
            self.poll_task.cancel()
            await asyncio.wait([self.poll_task])
        super().onLeave(details)

    async def onDisconnect(self):
        self.save()
        if self.poll_task:
            self.poll_task.cancel()
            await asyncio.wait([self.poll_task])
            await asyncio.sleep(0.5) # give others a chance to clean up

    async def _poll_step(self):
        # save changes
        if self.save_scheduled:
            self.save()
        # poll exporters
        for session in list(self.sessions.values()):
            if isinstance(session, ExporterSession):
                fut = self.call(
                    'org.labgrid.exporter.{}.version'.format(session.name)
                )
                done, _ = await asyncio.wait([fut], timeout=5)
                if not done:
                    print('kicking exporter ({}/{})'.format(session.key, session.name))
                    await self.on_session_leave(session.key)
                    continue
                try:
                    session.version = done.pop().result()
                except wamp.exception.ApplicationError as e:
                    if e.error == "wamp.error.no_such_procedure":
                        pass # old client
                    elif e.error == "wamp.error.canceled":
                        pass # disconnected
                    else:
                        raise

    async def poll(self):
        loop = asyncio.get_event_loop()
        while not loop.is_closed():
            try:
                await asyncio.sleep(15.0)
                await self._poll_step()
            except asyncio.CancelledError:
                break
            except Exception:  # pylint: disable=broad-except
                traceback.print_exc()

    def save_later(self):
        self.save_scheduled = True

    def save(self):
        self.save_scheduled = False
        with open('resources.yaml', 'w') as f:
            resources = self._get_resources()
            f.write(yaml.dump(resources, default_flow_style=False))
        with open('places.yaml', 'w') as f:
            places = self._get_places()
            f.write(yaml.dump(places, default_flow_style=False))

    def load(self):
        try:
            self.place = {}
            with open('places.yaml', 'r') as f:
                self.places = yaml.load(f.read())
            for placename, config in self.places.items():
                config['name'] = placename
                # FIXME maybe recover previously acquired places here?
                if 'acquired' in config:
                    del config['acquired']
                if 'acquired_resources' in config:
                    del config['acquired_resources']
                if 'allowed' in config:
                    del config['allowed']
                config['matches'] = [ResourceMatch(**match) for match in config['matches']]
                place = Place(**config)
                self.places[placename] = place
        except FileNotFoundError:
            pass

    def _add_default_place(self, name):
        if name in self.places:
            return
        if not name.isdigit():
            return
        place = Place(name)
        print(place)
        place.matches.append(ResourceMatch(exporter="*", group=name, cls="*"))
        self.places[name] = place

    async def _update_acquired_places(self, action, resource_path):
        """Update acquired places when resources are added or removed."""
        if action not in [Action.ADD, Action.DEL]:
            return  # currently nothing needed for Action.UPD
        for placename, place in self.places.items():
            if not place.acquired:
                continue
            if not place.hasmatch(resource_path):
                continue
            if action is Action.ADD:
                place.acquired_resources.append(resource_path)
            else:
                place.acquired_resources.remove(resource_path)
            self.publish(
                'org.labgrid.coordinator.place_changed', placename, place.asdict()
            )

    async def on_session_join(self, session_details):
        print('join')
        pprint(session_details)
        session = session_details['session']
        authid = session_details['authid']
        if authid.startswith('client/'):
            session = ClientSession(self, session, authid)
        elif authid.startswith('exporter/'):
            session = ExporterSession(self, session, authid)
        else:
            return
        self.sessions[session.key] = session

    async def on_session_leave(self, session_id):
        print('leave ({})'.format(session_id))
        try:
            session = self.sessions.pop(session_id)
        except KeyError:
            return
        if isinstance(session, ExporterSession):
            for groupname, group in session.groups.items():
                for resourcename in group.copy():
                    action, resource_path = session.set_resource(groupname, resourcename, {})
                    await self._update_acquired_places(action, resource_path)  # pylint: disable=not-an-iterable
        self.save_later()

    async def attach(self, name, details=None):
        # TODO check if name is in use
        session = self.sessions[details.caller]
        session_details = self.sessions[session]
        session_details['name'] = name
        self.exporters[name] = defaultdict(dict)

    async def set_resource(self, groupname, resourcename, resource, details=None):
        session = self.sessions.get(details.caller)
        if session is None:
            return
        assert isinstance(session, ExporterSession)

        groupname = str(groupname)
        resourcename = str(resourcename)
        # TODO check if acquired
        print(details)
        pprint(resource)
        action, resource_path = session.set_resource(groupname, resourcename, resource)
        if action is Action.ADD:
            self._add_default_place(groupname)
        await self._update_acquired_places(action, resource_path)  # pylint: disable=not-an-iterable
        self.save_later()

    def _get_resources(self):
        result = {}
        for session in self.sessions.values():
            if isinstance(session, ExporterSession):
                result[session.name] = session.get_resources()
        return result

    async def get_resources(self, details=None):
        return self._get_resources()

    async def add_place(self, name, details=None):
        if not name or not isinstance(name, str):
            return False
        if name in self.places:
            return False
        place = Place(name)
        self.places[name] = place
        self.publish(
            'org.labgrid.coordinator.place_changed', name, place.asdict()
        )
        self.save_later()
        return True

    async def del_place(self, name, details=None):
        if not name or not isinstance(name, str):
            return False
        if name not in self.places:
            return False
        del self.places[name]
        self.publish(
            'org.labgrid.coordinator.place_changed', name, {}
        )
        self.save_later()
        return True

    async def add_place_alias(self, placename, alias, details=None):
        try:
            place = self.places[placename]
        except KeyError:
            return False
        place.aliases.add(alias)
        place.touch()
        self.publish(
            'org.labgrid.coordinator.place_changed', placename, place.asdict()
        )
        self.save_later()
        return True

    async def del_place_alias(self, placename, alias, details=None):
        try:
            place = self.places[placename]
        except KeyError:
            return False
        try:
            place.aliases.remove(alias)
        except ValueError:
            return False
        place.touch()
        self.publish(
            'org.labgrid.coordinator.place_changed', placename, place.asdict()
        )
        self.save_later()
        return True

    async def set_place_comment(self, placename, comment, details=None):
        try:
            place = self.places[placename]
        except KeyError:
            return False
        place.comment = comment
        place.touch()
        self.publish(
            'org.labgrid.coordinator.place_changed', placename, place.asdict()
        )
        self.save_later()
        return True

    async def add_place_match(self, placename, pattern, rename=None, details=None):
        try:
            place = self.places[placename]
        except KeyError:
            return False
        match = ResourceMatch(*pattern.split('/'), rename=rename)
        if match in place.matches:
            return False
        place.matches.append(match)
        place.touch()
        self.publish(
            'org.labgrid.coordinator.place_changed', placename, place.asdict()
        )
        self.save_later()
        return True

    async def del_place_match(self, placename, pattern, rename=None, details=None):
        try:
            place = self.places[placename]
        except KeyError:
            return False
        match = ResourceMatch(*pattern.split('/'), rename=rename)
        try:
            place.matches.remove(match)
        except ValueError:
            return False
        place.touch()
        self.publish(
            'org.labgrid.coordinator.place_changed', placename, place.asdict()
        )
        self.save_later()
        return True

    async def acquire_place(self, name, details=None):
        print(details)
        try:
            place = self.places[name]
        except KeyError:
            return False
        if place.acquired:
            return False
        # FIXME use the session object instead? or something else which
        # survives disconnecting clients?
        place.acquired = self.sessions[details.caller].name
        for exporter, groups in self._get_resources().items():
            for group_name, group in sorted(groups.items()):
                for resource_name, resource in sorted(group.items()):
                    resource_path = (exporter, group_name, resource['cls'], resource_name)
                    if not place.hasmatch(resource_path):
                        continue
                    place.acquired_resources.append(resource_path)
        place.touch()
        self.publish(
            'org.labgrid.coordinator.place_changed', name, place.asdict()
        )
        self.save_later()
        return True

    async def release_place(self, name, details=None):
        print(details)
        try:
            place = self.places[name]
        except KeyError:
            return False
        if not place.acquired:
            return False
        place.acquired = None
        place.acquired_resources = []
        place.allowed = set()
        place.touch()
        self.publish(
            'org.labgrid.coordinator.place_changed', name, place.asdict()
        )
        self.save_later()
        return True

    async def allow_place(self, name, user, details=None):
        try:
            place = self.places[name]
        except KeyError:
            return False
        if not place.acquired:
            return False
        if not place.acquired == self.sessions[details.caller].name:
            return False
        place.allowed.add(user)
        place.touch()
        self.publish(
            'org.labgrid.coordinator.place_changed', name, place.asdict()
        )
        self.save_later()
        return True

    def _get_places(self):
        return {k: v.asdict() for k, v in self.places.items()}

    async def get_places(self, details=None):
        return self._get_places()


if __name__ == '__main__':
    runner = ApplicationRunner(
        url=environ.get("WS", u"ws://127.0.0.1:20408/ws"),
        realm="realm1",
    )
    runner.run(CoordinatorComponent)
