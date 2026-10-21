import os

import attrs

from labgrid.remote.auth.coordinator.claims import OAuth2JWTClaims
from labgrid.remote.auth.coordinator.oauth2 import (
    OAuth2ServerPlugin,
    ServerConfig,
    default_claims_to_clientIdentity,
    OAUTH2_PLUGIN_METADATA_KEY,
)

OAUTH2_PLUGIN_AUDIENCE_ENV_VAR = "LG_COORDINATOR_OAUTH2_PLUGIN_AUDIENCE"
OAUTH2_PLUGIN_ISSUER_ENV_VAR = "LG_COORDINATOR_OAUTH2_PLUGIN_ISSUER"
OAUTH2_PLUGIN_JWKS_URI_ENV_VAR = "LG_COORDINATOR_OAUTH2_PLUGIN_JWKS_URI"


@attrs.frozen
class OAuth2ServerPluginEnvVarConfig(ServerConfig):
    audience: str
    issuer: str
    jwks_uri: str

    @classmethod
    def from_env(cls, env: os._Environ[str]):
        audience = env.get(OAUTH2_PLUGIN_AUDIENCE_ENV_VAR)
        issuer = env.get(OAUTH2_PLUGIN_ISSUER_ENV_VAR)
        jwks_uri = env.get(OAUTH2_PLUGIN_JWKS_URI_ENV_VAR)

        if audience is None or issuer is None or jwks_uri is None:
            raise Exception(
                "Missing required environment variables: ensure LG_COORDINATOR_OAUTH2_PLUGIN_AUDIENCE,"
                "LG_COORDINATOR_OAUTH2_PLUGIN_ISSUER and LG_COORDINATOR_OAUTH2_PLUGIN_JWKS_URI are set"
            )

        return cls(audience=audience, issuer=issuer, jwks_uri=jwks_uri)


class OAuth2ServerPluginUsingEnvVars(OAuth2ServerPlugin):
    def __init__(self, env: os._Environ[str] = os.environ) -> None:
        super().__init__(config=OAuth2ServerPluginEnvVarConfig.from_env(env))
