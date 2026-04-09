import contextvars
import logging
from asyncio import iscoroutine

from grpc.aio import ServerInterceptor

from labgrid.remote.identity import ClientIdentity, NoIdentityPresent


class IdentityServerInterceptor(ServerInterceptor):
    def __init__(self, client_identity_contextvar: contextvars.ContextVar):
        super().__init__()
        self.client_identity_contextvar = client_identity_contextvar

    async def intercept_service(self, continuation, handler_call_details):
        # continuation may return a handler
        # OR an awaitable depending on grpcio build
        maybe_handler = continuation(handler_call_details)
        handler = await maybe_handler if iscoroutine(maybe_handler) else maybe_handler
        if handler is None:
            return None

        metadata = handler_call_details.invocation_metadata
        logging.debug(metadata)

        try:
            client_identity = ClientIdentity.from_metadata(metadata)
            logging.debug(client_identity)
            self.client_identity_contextvar.set(client_identity)
        except NoIdentityPresent:
            pass

        return handler
