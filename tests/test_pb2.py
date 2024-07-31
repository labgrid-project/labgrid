from labgrid.remote.common import Place, ResourceMatch, Reservation, set_map_from_dict, build_dict_from_map
import labgrid.remote.generated.labgrid_coordinator_pb2 as labgrid_coordinator_pb2

def test_place_as_pb2():
    place = Place(name="testing-place")
    pb2 = place.as_pb2()
    assert pb2.name == "testing-place"
    assert pb2.created == place.created
    assert pb2.changed == place.changed

def test_place_from_pb2():
    place_start = Place(name="testing-place", comment="such-comment")
    pb2 = place_start.as_pb2()
    assert pb2.name == "testing-place"
    place_new = Place.from_pb2(pb2)
    assert place_new.name == "testing-place"
    assert place_new.name == place_start.name
    assert place_new.comment == place_start.comment
    assert place_new.tags == place_start.tags
    assert place_new.matches == place_start.matches
    assert place_new.acquired == place_start.acquired
    assert place_new.acquired_resources == place_start.acquired_resources
    assert place_new.allowed == place_start.allowed
    assert place_new.created == place_start.created
    assert place_new.changed == place_start.changed
    assert place_new.reservation == place_start.reservation

def test_from_pb2_tags():
    tags = {"some": "test", "more": "values"}
    place_start = Place(name="testing-place", tags=tags)
    pb2 = place_start.as_pb2()
    assert pb2.name == "testing-place", f"PB2 has wrong name: {pb2}"
    assert pb2.tags is not None, f"PB2 has no tags field: {pb2}"
    place_new = Place.from_pb2(pb2)
    assert place_new.name == "testing-place"
    assert place_new.tags == place_start.tags
    assert place_new.tags == tags

def test_from_pb2_matches():
    rm = ResourceMatch("such", "test", "match")
    place_start = Place(name="testing-place", matches=[rm])
    pb2 = place_start.as_pb2()
    assert pb2.name == "testing-place", f"PB2 has wrong name: {pb2}"
    assert pb2.tags is not None, f"PB2 has no tags field: {pb2}"
    place_new = Place.from_pb2(pb2)
    assert place_new.name == "testing-place"
    assert place_new.tags == place_start.tags
    assert place_new.matches == place_start.matches

def test_from_pb2_tags_deepcopy():
    # Used by the RemotePlaceManager
    tags = {"some": "test", "more": "values"}
    place_start = Place(name="testing-place", tags=tags)
    pb2 = place_start.as_pb2()
    place_new = Place.from_pb2(pb2)
    import copy
    tags_copy = copy.deepcopy(place_new.tags)

def test_place_as_pb2_copy_with_match():
    tags = {"some": "test", "more": "values"}
    # Used by the RemotePlaceManager
    place_start = Place(name="testing-place", tags=tags, comment="Hello", aliases={"some": "alias"}, matches=[ResourceMatch("testporter","somegroup","someclass")])
    out = labgrid_coordinator_pb2.ClientOutMessage()

    update_response = labgrid_coordinator_pb2.UpdateResponse()
    update_response.place.CopyFrom(place_start.as_pb2())

    out.updates.append(update_response)

def test_match_as_from_pb2():
    rms = ResourceMatch("*", "somegroup", "someclass")
    pb2 = rms.as_pb2()
    assert pb2
    rme = ResourceMatch.from_pb2(pb2)
    assert rms == rme

def test_reservation_as_pb2():
    reservation = Reservation(
        owner="test",
        filters={
            "main": {"some": "filter"},
        },
        allocations={
            "main": ["the-place"],
        },
    )
    pb2 = reservation.as_pb2()
    assert pb2.owner == "test"
    assert pb2.token == reservation.token
    assert pb2.state == reservation.state.value
    assert pb2.filters["main"].filter == {"some": "filter"}
    assert pb2.created == reservation.created
    assert pb2.timeout == reservation.timeout

def test_reservation_as_from_pb2():
    resold = Reservation(
        owner="test",
        filters={
            "main": {"some": "filter"},
        },
        allocations={
            "main": ["the-place"],
        },
    )
    pb2 = resold.as_pb2()
    assert pb2.owner == resold.owner
    assert pb2.token == resold.token
    assert pb2.state == resold.state.value
    assert pb2.filters["main"].filter == {"some": "filter"}
    assert pb2.created == resold.created
    assert pb2.timeout == resold.timeout

    resnew = Reservation.from_pb2(pb2)

    assert resnew.owner == resold.owner
    assert resnew.token == resold.token
    assert resnew.state == resold.state
    assert resnew.filters["main"] == resold.filters["main"]
    assert resnew.created == resold.created
    assert resnew.timeout == resold.timeout

def test_resource_dict():
    params = {
        'host': 'foo',
        'model_id': 2277,
        'vendor_id': 1133,
        'path': None,
    }

    resource = labgrid_coordinator_pb2.Resource()
    set_map_from_dict(resource.params, params)
    bm = resource.SerializeToString()

    resource = labgrid_coordinator_pb2.Resource()
    resource.ParseFromString(bm)
    decoded = build_dict_from_map(resource.params)

    assert params == decoded

def test_map_serialize(benchmark):
    params = {
        'host': 'foo',
        'model_id': 2277,
        'vendor_id': 1133,
        'path': None,
    }

    def run():
        resource = labgrid_coordinator_pb2.Resource()
        set_map_from_dict(resource.params, params)
        bm = resource.SerializeToString()

    benchmark(run)

def test_map_deser(benchmark):
    params = {
        'host': 'foo',
        'model_id': 2277,
        'vendor_id': 1133,
        'path': None,
    }

    resource = labgrid_coordinator_pb2.Resource()
    set_map_from_dict(resource.params, params)
    bm = resource.SerializeToString()

    def run():
        resource = labgrid_coordinator_pb2.Resource()
        resource.ParseFromString(bm)
        decoded = build_dict_from_map(resource.params)

    benchmark(run)
