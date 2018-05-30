import socket
import time
from datetime import datetime
from fnmatch import fnmatchcase

import attr


@attr.s(cmp=False)
class ResourceEntry:
    data = attr.ib()  # cls, params
    acquired = attr.ib(default=None)

    def __attrs_post_init__(self):
        self.data.setdefault('avail', False)

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


@attr.s(cmp=True, repr=False, str=False)
# This class requires cmp=True, since we put the matches into a list and require
# the cmp functions to be able to remove the matches from the list later on.
class ResourceMatch:
    exporter = attr.ib()
    group = attr.ib()
    cls = attr.ib()
    name = attr.ib(default=None)
    # rename is just metadata, so don't use it for comparing matches
    rename = attr.ib(default=None, cmp=False)

    @classmethod
    def fromstr(cls, pattern):
        if not 2 <= pattern.count("/") <= 3:
            raise ValueError(
                "invalid pattern format '{}' (use 'exporter/group/cls/name')".
                format(pattern)
            )
        return cls(*pattern.split("/"))

    def __repr__(self):
        result = "{}/{}/{}".format(self.exporter, self.group, self.cls)
        if self.name is not None:
            result += "/{}".format(self.name)
        return result

    def __str__(self):
        result = repr(self)
        if self.rename:
            result += " → " + self.rename
        return result

    def ismatch(self, resource_path):
        """Return True if this matches the given resource"""
        exporter, group, cls, name = resource_path
        if not fnmatchcase(exporter, self.exporter):
            return False
        elif not fnmatchcase(group, self.group):
            return False
        elif not fnmatchcase(cls, self.cls):
            return False
        elif self.name and not fnmatchcase(name, self.name):
            return False

        return True


@attr.s(cmp=False)
class Place:
    name = attr.ib()
    aliases = attr.ib(default=attr.Factory(set), convert=set)
    comment = attr.ib(default="")
    matches = attr.ib(default=attr.Factory(list))
    acquired = attr.ib(default=None)
    acquired_resources = attr.ib(default=attr.Factory(list))
    allowed = attr.ib(default=attr.Factory(set), convert=set)
    created = attr.ib(default=attr.Factory(lambda: time.time()))
    changed = attr.ib(default=attr.Factory(lambda: time.time()))

    def asdict(self):
        result = attr.asdict(self)
        del result['name']  # the name is the key in the places dict
        return result

    def show(self, level=0):
        indent = '  ' * level
        print(indent + "aliases: {}".format(', '.join(self.aliases)))
        print(indent + "comment: {}".format(self.comment))
        print(indent + "matches:")
        for match in self.matches:
            print(indent + "  {}".format(match))
        print(indent + "acquired: {}".format(self.acquired))
        print(indent + "acquired resources:")
        for resource_path in self.acquired_resources:
            match = self.getmatch(resource_path)
            if match.rename:
                print(indent + "  {} → {}".format(
                    '/'.join(resource_path), match.rename))
            else:
                print(indent + "  {}".format(
                    '/'.join(resource_path)))
        print(indent + "allowed: {}".format(', '.join(self.allowed)))
        print(indent + "created: {}".format(datetime.fromtimestamp(self.created)))
        print(indent + "changed: {}".format(datetime.fromtimestamp(self.changed)))

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

    def touch(self):
        self.changed = time.time()

def enable_tcp_nodelay(session):
    """
    asyncio/autobahn does not set TCP_NODELAY by default, so we need to do it
    like this for now.
    """
    s = session._transport.transport.get_extra_info('socket')
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
