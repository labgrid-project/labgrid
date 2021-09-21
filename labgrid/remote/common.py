# pylint: disable=unsubscriptable-object
import socket
import time
import enum
import random
import re
import string
from datetime import datetime
from fnmatch import fnmatchcase

import attr

__all__ = [
    'TAG_KEY',
    'TAG_VAL',
    'ResourceEntry',
    'ResourceMatch',
    'Place',
    'ReservationState',
    'Reservation',
    'enable_tcp_nodelay',
]

TAG_KEY = re.compile(r"[a-z][a-z0-9_]+")
TAG_VAL = re.compile(r"[a-z0-9_]?")


@attr.s(eq=False)
class ResourceEntry:
    data = attr.ib()  # cls, params

    def __attrs_post_init__(self):
        self.data.setdefault('acquired', None)
        self.data.setdefault('avail', False)

    @property
    def acquired(self):
        return self.data['acquired']

    @property
    def avail(self):
        return self.data['avail']

    @property
    def cls(self):
        return self.data['cls']

    @property
    def params(self):
        return self.data['params']

    @property
    def args(self):
        """arguments for resource construction"""
        args = self.data['params'].copy()
        args.pop('extra', None)
        return args

    @property
    def extra(self):
        """extra resource information"""
        return self.data['params'].get('extra', {})

    def asdict(self):
        return {
            'cls': self.cls,
            'params': self.params,
            'acquired': self.acquired,
            'avail': self.avail,
        }

    def update(self, data):
        """apply updated information from the exporter on the coordinator"""
        data = data.copy()
        data.setdefault('acquired', None)
        data.setdefault('avail', False)
        self.data = data

    def acquire(self, place_name):
        assert self.data['acquired'] is None
        self.data['acquired'] = place_name

    def release(self):
        # ignore repeated releases
        self.data['acquired'] = None


@attr.s(eq=True, repr=False, str=False)
# This class requires eq=True, since we put the matches into a list and require
# the cmp functions to be able to remove the matches from the list later on.
class ResourceMatch:
    exporter = attr.ib()
    group = attr.ib()
    cls = attr.ib()
    name = attr.ib(default=None)
    # rename is just metadata, so don't use it for comparing matches
    rename = attr.ib(default=None, eq=False)

    @classmethod
    def fromstr(cls, pattern):
        if not 2 <= pattern.count("/") <= 3:
            raise ValueError(
                f"invalid pattern format '{pattern}' (use 'exporter/group/cls/name')"
            )
        return cls(*pattern.split("/"))

    def __repr__(self):
        result = f"{self.exporter}/{self.group}/{self.cls}"
        if self.name is not None:
            result += f"/{self.name}"
        return result

    def __str__(self):
        result = repr(self)
        if self.rename:
            result += " -> " + self.rename
        return result

    def ismatch(self, resource_path):
        """Return True if this matches the given resource"""
        exporter, group, cls, name = resource_path
        if not fnmatchcase(exporter, self.exporter):
            return False
        if not fnmatchcase(group, self.group):
            return False
        if not fnmatchcase(cls, self.cls):
            return False
        if self.name and not fnmatchcase(name, self.name):
            return False

        return True


@attr.s(eq=False)
class Place:
    name = attr.ib()
    aliases = attr.ib(default=attr.Factory(set), converter=set)
    comment = attr.ib(default="")
    tags = attr.ib(default=attr.Factory(dict))
    matches = attr.ib(default=attr.Factory(list))
    acquired = attr.ib(default=None)
    acquired_resources = attr.ib(default=attr.Factory(list))
    allowed = attr.ib(default=attr.Factory(set), converter=set)
    created = attr.ib(default=attr.Factory(time.time))
    changed = attr.ib(default=attr.Factory(time.time))
    reservation = attr.ib(default=None)

    def asdict(self):
        # in the coordinator, we have resource objects, otherwise just a path
        acquired_resources = []
        for resource in self.acquired_resources:  # pylint: disable=not-an-iterable
            if isinstance(resource, (tuple, list)):
                acquired_resources.append(resource)
            else:
                acquired_resources.append(resource.path)

        return {
            'aliases': list(self.aliases),
            'comment': self.comment,
            'tags': self.tags,
            'matches': [attr.asdict(x) for x in self.matches],
            'acquired': self.acquired,
            'acquired_resources': acquired_resources,
            'allowed': list(self.allowed),
            'created': self.created,
            'changed': self.changed,
            'reservation': self.reservation,
        }

    def update(self, config):
        fields = attr.fields_dict(type(self))
        for k, v in config.items():
            assert k in fields
            if k == 'name':
                # we cannot rename places
                assert v == self.name
                continue
            setattr(self, k, v)

    def show(self, level=0):
        indent = '  ' * level
        if self.aliases:
            print(indent + f"aliases: {', '.join(sorted(self.aliases))}")
        if self.comment:
            print(indent + f"comment: {self.comment}")
        if self.tags:
            print(indent + f"tags: {', '.join(k + '=' + v for k, v in sorted(self.tags.items()))}")
        print(indent + "matches:")
        for match in sorted(self.matches):  # pylint: disable=not-an-iterable
            print(indent + f"  {match}")
        print(indent + f"acquired: {self.acquired}")
        print(indent + "acquired resources:")
        # in the coordinator, we have resource objects, otherwise just a path
        for resource in sorted(self.acquired_resources):  # pylint: disable=not-an-iterable
            if isinstance(resource, (tuple, list)):
                resource_path = resource
            else:
                resource_path = resource.path
            match = self.getmatch(resource_path)
            if match.rename:
                print(indent + f"  {'/'.join(resource_path)} -> {match.rename}")
            else:
                print(indent + f"  {'/'.join(resource_path)}")
        if self.allowed:
            print(indent + f"allowed: {', '.join(self.allowed)}")
        print(indent + f"created: {datetime.fromtimestamp(self.created)}")
        print(indent + f"changed: {datetime.fromtimestamp(self.changed)}")
        if self.reservation:
            print(indent + f"reservation: {self.reservation}")

    def getmatch(self, resource_path):
        """Return the ResourceMatch object for the given resource path or None if not found.

        A resource_path has the structure (exporter, group, cls, name).
        """
        for match in self.matches:  # pylint: disable=not-an-iterable
            if match.ismatch(resource_path):
                return match

        return None

    def hasmatch(self, resource_path):
        """Return True if this place as a ResourceMatch object for the given resource path.

        A resource_path has the structure (exporter, group, cls, name).
        """
        return self.getmatch(resource_path) is not None

    def unmatched(self, resource_paths):
        """Returns a match which could not be matched to the list of resource_path

        A resource_path has the structure (exporter, group, cls, name).
        """
        for match in self.matches:
            if not any([match.ismatch(resource) for resource in resource_paths]):
                return match


    def touch(self):
        self.changed = time.time()


class ReservationState(enum.Enum):
    waiting = 0
    allocated = 1
    acquired = 2
    expired = 3
    invalid = 4


@attr.s(eq=False)
class Reservation:
    owner = attr.ib(validator=attr.validators.instance_of(str))
    token = attr.ib(default=attr.Factory(
        lambda: ''.join(random.choice(string.ascii_uppercase+string.digits) for i in range(10))))
    state = attr.ib(
        default='waiting',
        converter=lambda x: x if isinstance(x, ReservationState) else ReservationState[x],
        validator=attr.validators.instance_of(ReservationState))
    prio = attr.ib(default=0.0, validator=attr.validators.instance_of(float))
    # a dictionary of name -> filter dicts
    filters = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))
    # a dictionary of name -> place names
    allocations = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))
    created = attr.ib(default=attr.Factory(time.time))
    timeout = attr.ib(default=attr.Factory(lambda: time.time() + 60))

    def asdict(self):
        return {
            'owner': self.owner,
            'state': self.state.name,
            'prio': self.prio,
            'filters': self.filters,
            'allocations': self.allocations,
            'created': self.created,
            'timeout': self.timeout,
        }

    def refresh(self, delta=60):
        self.timeout = max(self.timeout, time.time() + delta)

    @property
    def expired(self):
        return self.timeout < time.time()

    def show(self, level=0):
        indent = '  ' * level
        print(indent + f"owner: {self.owner}")
        print(indent + f"token: {self.token}")
        print(indent + f"state: {self.state.name}")
        if self.prio:
            print(indent + f"prio: {self.prio}")
        print(indent + "filters:")
        for name, filter in self.filters.items():
            print(indent + f"  {name}: {' '.join([(k + '=' + v) for k, v in filter.items()])}")
        if self.allocations:
            print(indent + "allocations:")
            for name, allocation in self.allocations.items():
                print(indent + f"  {name}: {', '.join(allocation)}")
        print(indent + f"created: {datetime.fromtimestamp(self.created)}")
        print(indent + f"timeout: {datetime.fromtimestamp(self.timeout)}")


def enable_tcp_nodelay(session):
    """
    asyncio/autobahn does not set TCP_NODELAY by default, so we need to do it
    like this for now.
    """
    s = session._transport.transport.get_extra_info('socket')
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
