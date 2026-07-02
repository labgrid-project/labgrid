import pytest

from labgrid.remote.grpc.interceptor.client import (
    BaseIdentityClientInterceptor,
    IdentityClientUnaryUnaryInterceptor,
    IdentityClientStreamStreamInterceptor,
)
from labgrid.remote.identity import USERNAME_KEY, HOSTNAME_KEY, USER_AGENT_KEY


class DummyMetadata:
    def __init__(self):
        self.items = []

    def add(self, key, value):
        self.items.append((key, value))


class DummyClientCallDetails:
    def __init__(self):
        self.metadata = DummyMetadata()


def test_base_identity_client_interceptor_injects_all_fields():
    interceptor = BaseIdentityClientInterceptor(
        username="test_username",
        hostname="test_hostname",
        user_agent="test_agent",
    )

    client_call_details = DummyClientCallDetails()

    interceptor._inject(client_call_details)

    assert client_call_details.metadata.items == [
        (USERNAME_KEY, "test_username"),
        (HOSTNAME_KEY, "test_hostname"),
        (USER_AGENT_KEY, "test_agent"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "impl,method",
    [
        (IdentityClientUnaryUnaryInterceptor, "intercept_unary_unary"),
        (IdentityClientStreamStreamInterceptor, "intercept_stream_stream"),
    ],
)
async def test_client_interceptor_implementations(impl, method):
    interceptor = impl("test_username", "test_hostname", "test_agent")

    client_call_details = DummyClientCallDetails()
    request_or_iterator = object()
    sentinel_response = object()

    received = {}

    async def continuation(ccd, req):
        received["ccd"] = ccd
        received["req"] = req
        return sentinel_response

    interceptor_method = getattr(interceptor, method)
    result = await interceptor_method(continuation, client_call_details, request_or_iterator)

    assert result is sentinel_response
    assert received["ccd"] is client_call_details
    assert client_call_details.metadata.items == [
        (USERNAME_KEY, "test_username"),
        (HOSTNAME_KEY, "test_hostname"),
        (USER_AGENT_KEY, "test_agent"),
    ]
