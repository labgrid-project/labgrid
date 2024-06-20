import asyncio
import time
import enum
import random
import re
import string
import logging
from datetime import datetime
from fnmatch import fnmatchcase

import attr

from .generated import labgrid_coordinator_pb2

__all__ = [
    "TAG_KEY",
    "TAG_VAL",
    "ResourceEntry",
    "ResourceMatch",
    "Place",
    "ReservationState",
    "Reservation",
]

TAG_KEY = re.compile(r"[a-z][a-z0-9_]+")
TAG_VAL = re.compile(r"[a-z0-9_]?")


def set_map_from_dict(m, d):
    for k, v in d.items():
        assert isinstance(k, str)
        if v is None:
            m[k].Clear()
        elif isinstance(v, bool):
            m[k].bool_value = v
        elif isinstance(v, int):
            if v < 0:
                m[k].int_value = v
            else:
                m[k].uint_value = v
        elif isinstance(v, float):
            m[k].float_value = v
        elif isinstance(v, str):
            m[k].string_value = v
        else:
            raise ValueError(f"cannot translate {repr(v)} to MapValue")


def build_dict_from_map(m):
    d = {}
    for k, v in m.items():
        v: labgrid_coordinator_pb2.MapValue
        kind = v.WhichOneof("kind")
        if kind is None:
            d[k] = None
        else:
            d[k] = getattr(v, kind)
    return d


@attr.s(eq=False)
class ResourceEntry:
    data = attr.ib()  # cls, params

    def __attrs_post_init__(self):
        assert isinstance(self.data, dict)
        self.data.setdefault("acquired", None)
        self.data.setdefault("avail", False)

    @property
    def acquired(self):
        return self.data["acquired"]

    @property
    def avail(self):
        return self.data["avail"]

    @property
    def cls(self):
        return self.data["cls"]

    @property
    def params(self):
        return self.data["params"]

    @property
    def args(self):
        """arguments for resource construction"""
        args = self.data["params"].copy()
        args.pop("extra", None)
        return args

    @property
    def extra(self):
        """extra resource information"""
        return self.data["params"].get("extra", {})

    def asdict(self):
        return {
            "cls": self.cls,
            "params": self.params,
            "acquired": self.acquired,
            "avail": self.avail,
        }

    def update(self, data):
        """apply updated information from the exporter on the coordinator"""
        data = data.copy()
        data.setdefault("acquired", None)
        data.setdefault("avail", False)
        self.data = data

    def acquire(self, place_name):
        assert self.data["acquired"] is None
        self.data["acquired"] = place_name

    def release(self):
        # ignore repeated releases
        self.data["acquired"] = None

    def as_pb2(self):
        msg = labgrid_coordinator_pb2.Resource()
        msg.cls = self.cls
        params = self.params.copy()
        extra = params.pop("extra", {})
        set_map_from_dict(msg.params, params)
        set_map_from_dict(msg.extra, extra)
        if self.acquired is not None:
            msg.acquired = self.acquired
        msg.avail = self.avail
        return msg

    @staticmethod
    def data_from_pb2(pb2):
        assert isinstance(pb2, labgrid_coordinator_pb2.Resource)
        data = {
            "cls": pb2.cls,
            "params": build_dict_from_map(pb2.params),
            "acquired": pb2.acquired or None,
            "avail": pb2.avail,
        }
        data["params"]["extra"] = build_dict_from_map(pb2.extra)
        return data

    @classmethod
    def from_pb2(cls, pb2):
        assert isinstance(pb2, labgrid_coordinator_pb2.Place)
        return cls(cls.data_from_pb2(pb2))


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
            raise ValueError(f"invalid pattern format '{pattern}' (use 'exporter/group/cls/name')")
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
        try:
            exporter, group, cls, name = resource_path
        except ValueError:
            exporter, group, cls = resource_path
            name = None

        if not fnmatchcase(exporter, self.exporter):
            return False
        if not fnmatchcase(group, self.group):
            return False
        if not fnmatchcase(cls, self.cls):
            return False
        if name and self.name and not fnmatchcase(name, self.name):
            return False

        return True

    def as_pb2(self):
        return labgrid_coordinator_pb2.ResourceMatch(
            exporter=self.exporter,
            group=self.group,
            cls=self.cls,
            name=self.name,
            rename=self.rename,
        )

    @classmethod
    def from_pb2(cls, pb2):
        assert isinstance(pb2, labgrid_coordinator_pb2.ResourceMatch)
        return cls(
            exporter=pb2.exporter,
            group=pb2.group,
            cls=pb2.cls,
            name=pb2.name if pb2.HasField("name") else None,
            rename=pb2.rename,
        )


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
        for resource in self.acquired_resources:
            if isinstance(resource, (tuple, list)):
                acquired_resources.append(resource)
            else:
                acquired_resources.append(resource.path)

        return {
            "aliases": list(self.aliases),
            "comment": self.comment,
            "tags": self.tags,
            "matches": [attr.asdict(x) for x in self.matches],
            "acquired": self.acquired,
            "acquired_resources": acquired_resources,
            "allowed": list(self.allowed),
            "created": self.created,
            "changed": self.changed,
            "reservation": self.reservation,
        }

    def update_from_pb2(self, place_pb2):
        # FIXME untangle this...
        place = Place.from_pb2(place_pb2)
        fields = attr.fields_dict(type(self))
        for k, v in place.asdict().items():
            assert k in fields
            if k == "name":
                # we cannot rename places
                assert v == self.name
                continue
            if k == "matches":
                self.matches = [ResourceMatch.from_pb2(m) for m in place_pb2.matches]
                continue
            setattr(self, k, v)

    def show(self, level=0):
        indent = "  " * level
        if self.aliases:
            print(indent + f"aliases: {', '.join(sorted(self.aliases))}")
        if self.comment:
            print(indent + f"comment: {self.comment}")
        if self.tags:
            print(indent + f"tags: {', '.join(k + '=' + v for k, v in sorted(self.tags.items()))}")
        print(indent + "matches:")
        for match in sorted(self.matches):
            print(indent + f"  {match}")
        print(indent + f"acquired: {self.acquired}")
        print(indent + "acquired resources:")
        # in the coordinator, we have resource objects, otherwise just a path
        for resource in sorted(self.acquired_resources):
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
        for match in self.matches:
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

    def as_pb2(self):
        try:
            acquired_resources = []
            for resource in self.acquired_resources:
                assert not isinstance(resource, (tuple, list)), "as_pb2() only implemented for coordinator"
                assert len(resource.path) == 4
                path = "/".join(resource.path)
                acquired_resources.append(path)

            place = labgrid_coordinator_pb2.Place()
            place.name = self.name
            place.aliases.extend(self.aliases)
            place.comment = self.comment
            place.matches.extend(m.as_pb2() for m in self.matches)
            place.acquired = self.acquired or ""
            place.acquired_resources.extend(acquired_resources)
            place.allowed.extend(self.allowed)
            place.changed = self.changed
            place.created = self.created
            if self.reservation:
                place.reservation = self.reservation
            for key, value in self.tags.items():
                place.tags[key] = value
            return place
        except TypeError:
            logging.exception("failed to convert place %s to protobuf", self)
            raise

    @classmethod
    def from_pb2(cls, pb2):
        assert isinstance(pb2, labgrid_coordinator_pb2.Place)
        acquired_resources = []
        for path in pb2.acquired_resources:
            path = path.split("/")
            assert len(path) == 4
            acquired_resources.append(path)
        return cls(
            name=pb2.name,
            aliases=pb2.aliases,
            comment=pb2.comment,
            tags=dict(pb2.tags),
            matches=[ResourceMatch.from_pb2(m) for m in pb2.matches],
            acquired=pb2.acquired if pb2.HasField("acquired") and pb2.acquired else None,
            acquired_resources=acquired_resources,
            allowed=pb2.allowed,
            created=pb2.created,
            changed=pb2.changed,
            reservation=pb2.reservation if pb2.HasField("reservation") else None,
        )


class ReservationState(enum.Enum):
    waiting = 0
    allocated = 1
    acquired = 2
    expired = 3
    invalid = 4


@attr.s(eq=False)
class Reservation:
    owner = attr.ib(validator=attr.validators.instance_of(str))
    token = attr.ib(
        default=attr.Factory(lambda: "".join(random.choice(string.ascii_uppercase + string.digits) for i in range(10)))
    )
    state = attr.ib(
        default="waiting",
        converter=lambda x: x if isinstance(x, ReservationState) else ReservationState[x],
        validator=attr.validators.instance_of(ReservationState),
    )
    prio = attr.ib(default=0.0, validator=attr.validators.instance_of(float))
    # a dictionary of name -> filter dicts
    filters = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))
    # a dictionary of name -> place names
    allocations = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))
    created = attr.ib(default=attr.Factory(time.time))
    timeout = attr.ib(default=attr.Factory(lambda: time.time() + 60))

    def asdict(self):
        return {
            "owner": self.owner,
            "state": self.state.name,
            "prio": self.prio,
            "filters": self.filters,
            "allocations": self.allocations,
            "created": self.created,
            "timeout": self.timeout,
        }

    def refresh(self, delta=60):
        self.timeout = max(self.timeout, time.time() + delta)

    @property
    def expired(self):
        return self.timeout < time.time()

    def show(self, level=0):
        indent = "  " * level
        print(indent + f"owner: {self.owner}")
        print(indent + f"token: {self.token}")
        print(indent + f"state: {self.state.name}")
        if self.prio:
            print(indent + f"prio: {self.prio}")
        print(indent + "filters:")
        for name, fltr in self.filters.items():
            print(indent + f"  {name}: {' '.join([(k + '=' + v) for k, v in fltr.items()])}")
        if self.allocations:
            print(indent + "allocations:")
            for name, allocation in self.allocations.items():
                print(indent + f"  {name}: {', '.join(allocation)}")
        print(indent + f"created: {datetime.fromtimestamp(self.created)}")
        print(indent + f"timeout: {datetime.fromtimestamp(self.timeout)}")

    def as_pb2(self):
        res = labgrid_coordinator_pb2.Reservation()
        res.owner = self.owner
        res.token = self.token
        res.state = self.state.value
        res.prio = self.prio
        for name, fltr in self.filters.items():
            res.filters[name].CopyFrom(labgrid_coordinator_pb2.Reservation.Filter(filter=fltr))
        if self.allocations:
            # TODO: refactor to have only one place per filter group
            assert len(self.allocations) == 1
            assert "main" in self.allocations
            allocation = self.allocations["main"]
            assert len(allocation) == 1
            res.allocations.update({"main": allocation[0]})
        res.created = self.created
        res.timeout = self.timeout
        return res

    @classmethod
    def from_pb2(cls, pb2: labgrid_coordinator_pb2.Reservation):
        filters = {}
        for name, fltr_pb2 in pb2.filters.items():
            filters[name] = dict(fltr_pb2.filter)
        allocations = {}
        for fltr_name, place_name in pb2.allocations.items():
            allocations[fltr_name] = [place_name]
        return cls(
            owner=pb2.owner,
            token=pb2.token,
            state=ReservationState(pb2.state),
            prio=pb2.prio,
            filters=filters,
            allocations=allocations,
            created=pb2.created,
            timeout=pb2.timeout,
        )


async def queue_as_aiter(q):
    try:
        while True:
            try:
                item = await q.get()
            except asyncio.CancelledError:
                # gRPC doesn't like to receive exceptions from the request_iterator
                return
            if item is None:
                return
            yield item
            q.task_done()
            logging.debug("sent message %s", item)
    except Exception:
        logging.exception("error in queue_as_aiter")
        raise
