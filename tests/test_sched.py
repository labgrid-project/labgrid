from labgrid.remote.scheduler import *

def test_simple():
    places = [
        TagSet('place-1', {'name=place-1', 'soc=mx6'}),
        TagSet('place-2', {'name=place-2', 'soc=mx8'}),
    ]
    filters = [
        TagSet('res-1', {'soc=mx8'}),
        TagSet('res-2', {'soc=mx6'}),
    ]
    expected = {
        'res-1': 'place-2',
        'res-2': 'place-1',
    }

    assert schedule(places, filters) == expected
    assert schedule(places, filters[::-1]) == expected
    assert schedule(places[::-1], filters) == expected
    assert schedule(places[::-1], filters[::-1]) == expected


def test_overlap():
    places = [
        TagSet('place-1', {'name=place-1', 'soc=mx6', 'arch=arm'}),
        TagSet('place-2', {'name=place-2', 'soc=mx8', 'arch=arm'}),
    ]
    filters = [
        TagSet('res-1', {'arch=arm'}),
        TagSet('res-2', {'soc=mx6'}),
    ]
    expected = {
        'res-1': 'place-2',
        'res-2': 'place-1',
    }

    assert schedule(places, filters) == expected
    assert schedule(places, filters[::-1]) == expected
    assert schedule(places[::-1], filters) == expected
    assert schedule(places[::-1], filters[::-1]) == expected


def test_flexible():
    places = [
        TagSet('place-1', {'name=place-1', 'board=foo'}),
        TagSet('place-2', {'name=place-2', 'board=foo'}),
    ]
    filters = [
        TagSet('res-1', {'board=foo'}),
        TagSet('res-2', {'board=foo'}),
    ]
    expected_keys = {'res-1', 'res-2'}
    expected_vals = {'place-1', 'place-2'}

    allocation = schedule(places, filters)
    assert allocation.keys() == expected_keys
    assert set(allocation.values()) == expected_vals
    allocation = schedule(places, filters[::-1])
    assert allocation.keys() == expected_keys
    assert set(allocation.values()) == expected_vals
    allocation = schedule(places[::-1], filters)
    assert allocation.keys() == expected_keys
    assert set(allocation.values()) == expected_vals
    allocation = schedule(places[::-1], filters[::-1])
    assert allocation.keys() == expected_keys
    assert set(allocation.values()) == expected_vals


def test_conflict():
    places = [
        TagSet('place-1', {'name=place-1', 'board=foo'}),
    ]
    filters = [
        TagSet('res-1', {'board=foo'}),
        TagSet('res-2', {'board=foo'}),
    ]

    assert schedule(places, filters) == {'res-1': 'place-1'}
    assert schedule(places, filters[::-1]) == {'res-2': 'place-1'}
    assert schedule(places[::-1], filters) == {'res-1': 'place-1'}
    assert schedule(places[::-1], filters[::-1]) == {'res-2': 'place-1'}
