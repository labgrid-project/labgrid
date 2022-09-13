from collections import defaultdict

import attr


@attr.s(eq=False)
class TagSet:
    name = attr.ib(validator=attr.validators.instance_of(str))
    tags = attr.ib(validator=attr.validators.instance_of(set))


def schedule_step(places, filters):
    "Find the filters that can be directly allocated without overlap."
    interest = defaultdict(list)
    for f in filters:
        for place in places:
            if f.tags.issubset(place.tags):
                interest[place].append(f)

    if not interest:
        return {}

    limit = min(map(len, interest.values()))
    allocation = {}
    for interest_place, interest_filters in interest.items():
        if len(interest_filters) == limit:
            allocation[interest_filters.pop(0)] = interest_place

    return allocation


def schedule_overlaps(places, filters):
    "Iterate schedule_step until no more allocations are found."
    places = places[:]
    filters = filters[:]
    allocation = {}
    while True:
        new = schedule_step(places, filters)
        if not new:
            break
        for f, place in new.items():
            assert f not in allocation
            places.remove(place)
            filters.remove(f)
            allocation[f] = place
    return allocation


def schedule(places, filters):
    allocation = schedule_overlaps(places, filters)
    return {f.name: p.name for f, p in allocation.items()}
