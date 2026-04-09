import contextvars, pytest
from types import SimpleNamespace
from unittest.mock import Mock
from labgrid.remote.grpc.interceptor.server import IdentityServerInterceptor


@pytest.fixture
def cv():
    return contextvars.ContextVar("client_identity", default=None)


@pytest.fixture
def interceptor(cv):
    return IdentityServerInterceptor(cv)


def handler_call_details(metadata):
    return SimpleNamespace(invocation_metadata=tuple(metadata))


@pytest.mark.asyncio
async def test_server_interceptor_sets_contextvar(interceptor, cv):
    handler = object()
    continuation = Mock(return_value=handler)

    metadata = (("x-lg-hostname", "h"), ("x-lg-username", "u"), ("x-lg-user-agent", "ua"))

    ret = await interceptor.intercept_service(continuation, handler_call_details(metadata))
    assert ret is handler

    identity = cv.get()
    assert identity.id == "h/u"
    assert identity.user_agent == "ua"
