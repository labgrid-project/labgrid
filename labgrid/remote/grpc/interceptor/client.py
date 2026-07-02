from typing import Optional

from grpc.aio import ClientCallDetails, ClientInterceptor, StreamStreamClientInterceptor, UnaryUnaryClientInterceptor

from labgrid.remote.identity import HOSTNAME_KEY, USER_AGENT_KEY, USERNAME_KEY


class BaseIdentityClientInterceptor(ClientInterceptor):
    def __init__(self, username: Optional[str], hostname: str, user_agent: Optional[str]):
        super().__init__()
        self.username = username
        self.hostname = hostname
        self.user_agent = user_agent

    def _inject(self, client_call_details: ClientCallDetails):
        if self.username:
            client_call_details.metadata.add(USERNAME_KEY, self.username)
        client_call_details.metadata.add(HOSTNAME_KEY, self.hostname)
        if self.user_agent:
            client_call_details.metadata.add(USER_AGENT_KEY, self.user_agent)


class IdentityClientUnaryUnaryInterceptor(UnaryUnaryClientInterceptor, BaseIdentityClientInterceptor):
    async def intercept_unary_unary(self, continuation, client_call_details, request):
        self._inject(client_call_details)
        return await continuation(client_call_details, request)


class IdentityClientStreamStreamInterceptor(StreamStreamClientInterceptor, BaseIdentityClientInterceptor):
    async def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        self._inject(client_call_details)
        return await continuation(client_call_details, request_iterator)
