import argparse
import asyncio

import grpc
import pytest
import pytest_asyncio

from labgrid.remote.coordinator import Coordinator, client_identity_context
from labgrid.remote.client import ClientSession, ServerError, UserError
from labgrid.remote.grpc.interceptor.server import IdentityServerInterceptor
from labgrid.remote.generated import labgrid_coordinator_pb2
from labgrid.remote.generated import labgrid_coordinator_pb2_grpc

@pytest_asyncio.fixture(loop_scope='function')
async def coordinator():
    coordinator = Coordinator(True)
    server = grpc.aio.server(
        interceptors=[IdentityServerInterceptor(client_identity_context)],
    )
    labgrid_coordinator_pb2_grpc.add_CoordinatorServicer_to_server(coordinator, server)
    server.add_insecure_port("[::]:20408")
    await server.start()
    yield coordinator
    await server.stop(5)

@pytest_asyncio.fixture(loop_scope='function')
async def client():
    loop = asyncio.get_running_loop()
    client = ClientSession("127.0.0.1:20408", loop=loop)
    await client.start()
    yield client
    await client.stop()

async def test_cap_add_place(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()
    place = client.get_place("testplace")
    assert place is not None

async def test_cap_acquire_place(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()

    await client.acquire()
    place = client.get_place("testplace")
    assert place.acquired is not None

async def test_cap_release_place(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()

    await client.acquire()
    place = client.get_place("testplace")
    assert place.acquired is not None

    await client.release()
    place = client.get_place("testplace")
    assert place.acquired is None

async def test_cap_delete_place(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()

    await client.del_place()

async def test_cap_add_place_alias(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.alias = "testalias"
    client.args = args
    await client.add_place()

    await client.add_alias()

async def test_cap_del_place_alias(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.alias = "testalias"
    client.args = args
    await client.add_place()

    await client.add_alias()

    await client.del_alias()

async def test_cap_add_place_match(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.patterns = [ "my/test/pattern/" ]
    client.args = args
    await client.add_place()

    await client.add_match()

    place = client.get_place("testplace")
    assert place.matches is not None, place.matches

async def test_cap_del_place_match(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.patterns = [ "my/test/pattern/" ]
    client.args = args
    await client.add_place()

    await client.add_match()

    place = client.get_place("testplace")
    assert place.matches is not None, place.matches

    await client.del_match()
    place = client.get_place("testplace")
    assert len(place.matches) == 0, place.matches

async def test_cap_create_reservation(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.user = "testhost/testuser"
    args.prio = 10
    args.shell = False
    args.wait = False
    client.args = args
    args.filters = ["name=someplace"]
    await client.add_place()

    await client.create_reservation()

async def test_cap_cancel_reservation(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.user = "testhost/testuser"
    args.prio = 10
    args.shell = False
    args.wait = False
    client.args = args
    args.filters = ["name=someplace"]
    await client.add_place()

    token = await client.create_reservation()

    client.args.token = token

    await client.cancel_reservation()

async def test_cap_print_reservation(coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.user = "testhost/testuser"
    args.prio = 10
    args.shell = False
    args.wait = False
    client.args = args
    args.filters = ["name=someplace"]
    await client.add_place()

    token = await client.create_reservation()

    await client.print_reservations()
