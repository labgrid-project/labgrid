import logging

from grpc.aio import ClientCallDetails, ClientInterceptor, StreamStreamClientInterceptor, UnaryUnaryClientInterceptor

from labgrid.remote.auth.plugin import ClientAuthPlugin


class BaseIdentityClientInterceptor(ClientInterceptor):
    logger = logging.getLogger(__name__)

    def __init__(self, plugin: ClientAuthPlugin):
        super().__init__()
        self.plugin = plugin

    def _inject(self, client_call_details: ClientCallDetails):
        metadata_to_inject = self.plugin.metadata()
        self.logger.debug("Metadata from plugin: %s", metadata_to_inject)
        for k, vs in metadata_to_inject.items():
            for v in vs:
                client_call_details.metadata.add(k, v)
        self.logger.debug("RPC metadata after modifications: %s", client_call_details.metadata)


class IdentityClientUnaryUnaryInterceptor(UnaryUnaryClientInterceptor, BaseIdentityClientInterceptor):
    async def intercept_unary_unary(self, continuation, client_call_details, request):
        self._inject(client_call_details)
        return await continuation(client_call_details, request)


class IdentityClientStreamStreamInterceptor(StreamStreamClientInterceptor, BaseIdentityClientInterceptor):
    async def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        self._inject(client_call_details)
        return await continuation(client_call_details, request_iterator)
