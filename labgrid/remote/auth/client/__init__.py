import os
from typing import List, Mapping

import jwt

from labgrid.remote.auth.coordinator import OAuth2JWTClaims
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

    def _access_token_to_claims(self, token: str) -> OAuth2JWTClaims:
        claims_dict = jwt.decode(token, options={"verify_signature": False})
        return OAuth2JWTClaims.model_validate(claims_dict)

    def identity_id(self) -> str:
        claims = self._access_token_to_claims(self.metadata()["access-token"][0])
        return claims.sub
