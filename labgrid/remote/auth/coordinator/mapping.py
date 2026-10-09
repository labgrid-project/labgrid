from typing import Mapping, Set

import attrs
from labgrid.remote.auth.capability import Capability


@attrs.define(eq=True)
class RoleMapping:
    mapping: Mapping[str, Set[Capability]] = attrs.field()

    def __call__(self, roles: Set[str]) -> Set[Capability]:
        capabilities = set()
        for role in roles:
            to_add = self.mapping.get(role)
            if to_add:
                capabilities.update(to_add)
        return capabilities
