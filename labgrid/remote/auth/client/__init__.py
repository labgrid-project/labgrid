import os
from typing import List, Mapping

from labgrid.remote.auth.plugin import ClientAuthPlugin

OAUTH2_PLUGIN_ACCESS_TOKEN_ENV_VAR = "LG_CLIENT_OAUTH2_PLUGIN_ACCESS_TOKEN"


class OAuth2ClientPluginUsingEnvVars(ClientAuthPlugin):
    def __init__(self, env: os._Environ[str] = os.environ) -> None:
        self.env = env

    def metadata(self) -> Mapping[str, List[str]]:
        access_token = self.env.get(OAUTH2_PLUGIN_ACCESS_TOKEN_ENV_VAR)

        if access_token is None:
            raise Exception(
                "Missing required environment variables: ensure LG_CLIENT_OAUTH2_PLUGIN_ACCESS_TOKEN is set"
            )

        return {"access-token": [access_token]}
