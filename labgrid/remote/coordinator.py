"""The coordinator module coordinates exported resources and clients accessing them."""
# pylint: disable=no-member,unused-argument
import asyncio
import traceback
from collections import defaultdict
from os import environ
from pprint import pprint
from enum import Enum
from functools import wraps

import attr
import yaml
from autobahn import wamp
from autobahn.asyncio.wamp import ApplicationRunner, ApplicationSession
from autobahn.wamp.types import RegisterOptions

from .common import *
from .scheduler import TagSet, schedule
from ..util import atomic_replace


class Action(Enum):
    ADD = 0
    DEL = 1
    UPD = 2


@attr.s(init=False, eq=False)
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


@attr.s(eq=False)
class ExporterSession(RemoteSession):
    """An ExporterSession is opened for each Exporter connecting to the
    coordinator, allowing the Exporter to get and set resources"""
    groups = attr.ib(default=attr.Factory(dict), init=False)

    def set_resource(self, groupname, resourcename, resourcedata):
        group = self.groups.setdefault(groupname, {})
        old = group.get(resourcename)
        if resourcedata and old:
            old.update(resourcedata)
            new = old
        elif resourcedata and not old:
            new = group[resourcename] = ResourceImport(
                resourcedata,
                path=(self.name, groupname, resourcedata['cls'], resourcename)
            )
        elif not resourcedata and old:
            new = None
            del group[resourcename]
        else:
            assert not resourcedata and not old
            new = None

        self.coordinator.publish(
            'org.labgrid.coordinator.resource_changed', self.name,
            groupname, resourcename, new.asdict() if new else {}
        )

        if old and new:
            assert old is new
            return Action.UPD, new
        elif old and not new:
            return Action.DEL, old
        elif not old and new:
            return Action.ADD, new

        assert not old and not new

    def get_resources(self):
        """Method invoked by the client, get the resources from the coordinator"""
        result = {}
        for groupname, group in self.groups.items():
            result_group = result[groupname] = {}
            for resourcename, resource in group.items():
                result_group[resourcename] = resource.asdict()
        return result


@attr.s(eq=False)
class ClientSession(RemoteSession):
    pass


@attr.s(eq=False)
class ResourceImport(ResourceEntry):
    """Represents a local resource exported from an exporter.

    The ResourceEntry attributes contain the information for the client.
    """
    path = attr.ib(kw_only=True, validator=attr.validators.instance_of(tuple))


def locked(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        async with self.lock:
            return await func(self, *args, **kwargs)
    return wrapper

class CoordinatorComponent(ApplicationSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = asyncio.Lock()

    @locked
    async def onConnect(self):
        self.sessions = {}
        self.places = {}
        self.reservations = {}
        self.poll_task = None
        self.save_scheduled = False

        self.load()
        self.save_later()

        enable_tcp_nodelay(self)
        self.join(self.config.realm, ["ticket"], "coordinator")

    def onChallenge(self, challenge):
        return "dummy-ticket"

    @locked
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
            self.set_place_tags, 'org.labgrid.coordinator.set_place_tags'
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

        # reservations
        await self.register(
            self.create_reservation,
            'org.labgrid.coordinator.create_reservation',
            options=RegisterOptions(details_arg='details'),
        )
        await self.register(
            self.cancel_reservation,
            'org.labgrid.coordinator.cancel_reservation',
        )
        await self.register(
            self.poll_reservation,
            'org.labgrid.coordinator.poll_reservation',
        )
        await self.register(
            self.get_reservations,
            'org.labgrid.coordinator.get_reservations',
        )

        self.poll_task = asyncio.get_event_loop().create_task(self.poll())

        print("Coordinator ready.")

    @locked
    async def onLeave(self, details):
        await self.save()
        if self.poll_task:
            self.poll_task.cancel()
            await asyncio.wait([self.poll_task])
        super().onLeave(details)

    @locked
    async def onDisconnect(self):
        await self.save()
        if self.poll_task:
            self.poll_task.cancel()
            await asyncio.wait([self.poll_task])
            await asyncio.sleep(0.5) # give others a chance to clean up

    async def _poll_step(self):
        # save changes
        if self.save_scheduled:
            await self.save()
        # poll exporters
        for session in list(self.sessions.values()):
            if isinstance(session, ExporterSession):
                fut = self.call(
                    f'org.labgrid.exporter.{session.name}.version'
                )
                done, _ = await asyncio.wait([fut], timeout=5)
                if not done:
                    print(f'kicking exporter ({session.key}/{session.name})')
                    await self.call('wamp.session.kill', session.key, message="timeout detected by coordinator")
                    print(f'cleaning up exporter ({session.key}/{session.name})')
                    await self.on_session_leave(session.key)
                    print(f'removed exporter ({session.key}/{session.name})')
                    continue
                try:
                    session.version = done.pop().result()
                except wamp.exception.ApplicationError as e:
                    if e.error == "wamp.error.no_such_procedure":
                        pass # old client
                    elif e.error == "wamp.error.canceled":
                        pass # disconnected
                    elif e.error == "wamp.error.no_such_session":
                        pass # client has already disconnected
                    else:
                        raise
        # update reservations
        self.schedule_reservations()

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

    async def save(self):
        self.save_scheduled = False

        resources = self._get_resources()
        resources = yaml.dump(resources, default_flow_style=False)
        resources = resources.encode()
        places = self._get_places()
        places = yaml.dump(places, default_flow_style=False)
        places = places.encode()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, atomic_replace, 'resources.yaml', resources)
        await loop.run_in_executor(None, atomic_replace, 'places.yaml', places)

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
                if 'reservation' in config:
                    del config['reservation']
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

    async def _update_acquired_places(self, action, resource, callback=True):
        """Update acquired places when resources are added or removed."""
        if action not in [Action.ADD, Action.DEL]:
            return  # currently nothing needed for Action.UPD

        # collect affected places
        places = []
        for place in self.places.values():
            if not place.acquired:
                continue
            if not place.hasmatch(resource.path):
                continue
            places.append(place)

        if action is Action.ADD:
            # only add if there is no conflict
            if len(places) != 1:
                return
            place = places[0]
            await self._acquire_resources(place, [resource])
            self._publish_place(place)
        else:
            for place in places:
                await self._release_resources(place, [resource], callback=callback)
                self._publish_place(place)

    def _publish_place(self, place):
        self.publish(
            'org.labgrid.coordinator.place_changed', place.name, place.asdict()
        )

    def _publish_resource(self, resource):
        self.publish(
            'org.labgrid.coordinator.resource_changed',
            resource.path[0], # exporter name
            resource.path[1], # group name
            resource.path[3], # resource name
            resource.asdict(),
        )

    @locked
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

    @locked
    async def on_session_leave(self, session_id):
        print(f'leave ({session_id})')
        try:
            session = self.sessions.pop(session_id)
        except KeyError:
            return
        if isinstance(session, ExporterSession):
            for groupname, group in session.groups.items():
                for resourcename in group.copy():
                    action, resource = session.set_resource(groupname, resourcename, {})
                    await self._update_acquired_places(action, resource, callback=False)  # pylint: disable=not-an-iterable
        self.save_later()

    @locked
    async def attach(self, name, details=None):
        # TODO check if name is in use
        session = self.sessions[details.caller]
        session_details = self.sessions[session]
        session_details['name'] = name
        self.exporters[name] = defaultdict(dict)

    # not @locked because set_resource my be triggered by a acquire() call to
    # an exporter, leading to a deadlock on acquire_place()
    async def set_resource(self, groupname, resourcename, resourcedata, details=None):
        """Called by exporter to create/update/remove resources."""
        session = self.sessions.get(details.caller)
        if session is None:
            return
        assert isinstance(session, ExporterSession)

        groupname = str(groupname)
        resourcename = str(resourcename)
        # TODO check if acquired
        print(details)
        pprint(resourcedata)
        action, resource = session.set_resource(groupname, resourcename, resourcedata)
        if action is Action.ADD:
            async with self.lock:
                self._add_default_place(groupname)
        if action in (Action.ADD, Action.DEL):
            async with self.lock:
                await self._update_acquired_places(action, resource)  # pylint: disable=not-an-iterable
        self.save_later()

    def _get_resources(self):
        result = {}
        for session in self.sessions.values():
            if isinstance(session, ExporterSession):
                result[session.name] = session.get_resources()
        return result

    @locked
    async def get_resources(self, details=None):
        return self._get_resources()

    @locked
    async def add_place(self, name, details=None):
        if not name or not isinstance(name, str):
            return False
        if name in self.places:
            return False
        place = Place(name)
        self.places[name] = place
        self._publish_place(place)
        self.save_later()
        return True

    @locked
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

    @locked
    async def add_place_alias(self, placename, alias, details=None):
        try:
            place = self.places[placename]
        except KeyError:
            return False
        place.aliases.add(alias)
        place.touch()
        self._publish_place(place)
        self.save_later()
        return True

    @locked
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
        self._publish_place(place)
        self.save_later()
        return True

    @locked
    async def set_place_tags(self, placename, tags, details=None):
        try:
            place = self.places[placename]
        except KeyError:
            return False
        assert isinstance(tags, dict)
        for k, v in tags.items():
            assert isinstance(k, str)
            assert isinstance(v, str)
            if not TAG_KEY.match(k):
                return False
            if not TAG_VAL.match(v):
                return False
        for k, v in tags.items():
            if not v:
                try:
                    del place.tags[k]
                except KeyError:
                    pass
            else:
                place.tags[k] = v
        place.touch()
        self._publish_place(place)
        self.save_later()
        return True

    @locked
    async def set_place_comment(self, placename, comment, details=None):
        try:
            place = self.places[placename]
        except KeyError:
            return False
        place.comment = comment
        place.touch()
        self._publish_place(place)
        self.save_later()
        return True

    @locked
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
        self._publish_place(place)
        self.save_later()
        return True

    @locked
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
        self._publish_place(place)
        self.save_later()
        return True

    async def _acquire_resources(self, place, resources):
        resources = resources.copy() # we may modify the list
        # all resources need to be free
        for resource in resources:
            if resource.acquired:
                return False

        # acquire resources
        acquired = []
        try:
            for resource in resources:
                # this triggers an update from the exporter which is published
                # to the clients
                await self.call(f'org.labgrid.exporter.{resource.path[0]}.acquire',
                                resource.path[1], resource.path[3], place.name)
                acquired.append(resource)
        except:
            print(f"failed to acquire {resource}")
            # cleanup
            await self._release_resources(place, acquired)
            return False

        for resource in resources:
            place.acquired_resources.append(resource)

        return True

    async def _release_resources(self, place, resources, callback=True):
        resources = resources.copy() # we may modify the list

        for resource in resources:
            try:
                place.acquired_resources.remove(resource)
            except ValueError:
                pass

        for resource in resources:
            try:
                # this triggers an update from the exporter which is published
                # to the clients
                if callback:
                    await self.call(f'org.labgrid.exporter.{resource.path[0]}.release',
                                    resource.path[1], resource.path[3])
            except:
                print(f"failed to release {resource}")
                # at leaset try to notify the clients
                try:
                    self._publish_resource(resource)
                except:
                    pass

    @locked
    async def acquire_place(self, name, details=None):
        print(details)
        try:
            place = self.places[name]
        except KeyError:
            return False
        if place.acquired:
            return False
        if place.reservation:
            res = self.reservations[place.reservation]
            if not res.owner == self.sessions[details.caller].name:
                return False
        # FIXME use the session object instead? or something else which
        # survives disconnecting clients?
        place.acquired = self.sessions[details.caller].name
        resources = []
        for _, session in sorted(self.sessions.items()):
            if not isinstance(session, ExporterSession):
                continue
            for _, group in sorted(session.groups.items()):
                for _, resource in sorted(group.items()):
                    if not place.hasmatch(resource.path):
                        continue
                    resources.append(resource)
        if not await self._acquire_resources(place, resources):
            # revert earlier change
            place.acquired = None
            return False
        place.touch()
        self._publish_place(place)
        self.save_later()
        self.schedule_reservations()
        return True

    @locked
    async def release_place(self, name, details=None):
        print(details)
        try:
            place = self.places[name]
        except KeyError:
            return False
        if not place.acquired:
            return False

        await self._release_resources(place, place.acquired_resources)

        place.acquired = None
        place.allowed = set()
        place.touch()
        self._publish_place(place)
        self.save_later()
        self.schedule_reservations()
        return True

    @locked
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
        self._publish_place(place)
        self.save_later()
        return True

    def _get_places(self):
        return {k: v.asdict() for k, v in self.places.items()}

    @locked
    async def get_places(self, details=None):
        return self._get_places()

    def schedule_reservations(self):
        # The primary information is stored in the reservations and the places
        # only have a copy for convenience.

        # expire reservations
        for res in list(self.reservations.values()):
            if res.state is ReservationState.acquired:
                # acquired reservations do not expire
                res.refresh()
            if not res.expired:
                continue
            if res.state is not ReservationState.expired:
                res.state = ReservationState.expired
                res.allocations.clear()
                res.refresh()
                print(f'reservation ({res.owner}/{res.token}) is now {res.state.name}')
            else:
                del self.reservations[res.token]
                print(f'removed {res.state.name} reservation ({res.owner}/{res.token})')

        # check which places are already allocated and handle state transitions
        allocated_places = set()
        for res in self.reservations.values():
            acquired_places = set()
            for group in list(res.allocations.values()):
                for name in group:
                    place = self.places.get(name)
                    if place is None:
                        # the allocated place was deleted
                        res.state = ReservationState.invalid
                        res.allocations.clear()
                        res.refresh(300)
                        print(f'reservation ({res.owner}/{res.token}) is now {res.state.name}')
                    if place.acquired is not None:
                        acquired_places.add(name)
                    assert name not in allocated_places, "conflicting allocation"
                    allocated_places.add(name)
            if acquired_places and res.state is ReservationState.allocated:
                # an allocated place was acquired
                res.state = ReservationState.acquired
                res.refresh()
                print(f'reservation ({res.owner}/{res.token}) is now {res.state.name}')
            if not acquired_places and res.state is ReservationState.acquired:
                # all allocated places were released
                res.state = ReservationState.allocated
                res.refresh()
                print(f'reservation ({res.owner}/{res.token}) is now {res.state.name}')

        # check which places are available for allocation
        available_places = set()
        for name, place in self.places.items():
            if place.acquired is None and place.reservation is None:
                available_places.add(name)
        assert not (available_places & allocated_places), "inconsistent allocation"
        available_places -= allocated_places

        # check which reservations should be handled, ordered by priority and age
        pending_reservations = []
        for res in sorted(self.reservations.values(), key=lambda x: (-x.prio, x.created)):
            if res.state is not ReservationState.waiting:
                continue
            pending_reservations.append(res)

        # run scheduler
        place_tagsets = []
        for name in available_places:
            tags = set(self.places[name].tags.items())
            # support place names
            tags |= {('name', name)}
            # support place aliases
            place_tagsets.append(TagSet(name, tags))
        filter_tagsets = []
        for res in pending_reservations:
            filter_tagsets.append(TagSet(res.token, set(res.filters['main'].items())))
        allocation = schedule(place_tagsets, filter_tagsets)

        # apply allocations
        for res_token, place_name in allocation.items():
            res = self.reservations[res_token]
            res.allocations = {'main': [place_name]}
            res.state = ReservationState.allocated
            res.refresh()
            print(f'reservation ({res.owner}/{res.token}) is now {res.state.name}')

        # update reservation property of each place and notify
        old_map = {}
        for place in self.places.values():
            old_map[place.name] = place.reservation
            place.reservation = None
        new_map = {}
        for res in self.reservations.values():
            if not res.allocations:
                continue
            assert len(res.allocations) == 1, "only one filter group is implemented"
            for group in res.allocations.values():
                for name in group:
                    assert name not in new_map, "conflicting allocation"
                    new_map[name] = res.token
                    place = self.places.get(name)
                    assert place is not None, "invalid allocation"
                    place.reservation = res.token
        for name in old_map.keys() | new_map.keys():
            if old_map.get(name) != new_map.get(name):
                self._publish_place(place)

    @locked
    async def create_reservation(self, spec, prio=0.0, details=None):
        filter_ = {}
        for pair in spec.split():
            try:
                k, v = pair.split('=')
            except ValueError:
                return None
            if not TAG_KEY.match(k):
                return None
            if not TAG_VAL.match(v):
                return None
            filter_[k] = v

        filters = {'main': filter_} # currently, only one group is implemented

        owner = self.sessions[details.caller].name
        res = Reservation(owner=owner, prio=prio, filters=filters)
        self.reservations[res.token] = res
        self.schedule_reservations()
        return {res.token: res.asdict()}

    @locked
    async def cancel_reservation(self, token, details=None):
        if not isinstance(token, str):
            return False
        if token not in self.reservations:
            return False
        del self.reservations[token]
        self.schedule_reservations()
        return True

    @locked
    async def poll_reservation(self, token, details=None):
        try:
            res = self.reservations[token]
        except KeyError:
            return None
        res.refresh()
        return res.asdict()

    @locked
    async def get_reservations(self, details=None):
        return {k: v.asdict() for k, v in self.reservations.items()}

if __name__ == '__main__':
    runner = ApplicationRunner(
        url=environ.get("WS", u"ws://127.0.0.1:20408/ws"),
        realm="realm1",
    )
    runner.run(CoordinatorComponent)
