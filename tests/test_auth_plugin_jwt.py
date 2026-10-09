from datetime import datetime, timedelta, timezone

import attrs
import jwt
from jwcrypto import jwk
from jwt import PyJWK
from pydantic import BaseModel

from labgrid.remote.auth.capability import Capability
from labgrid.remote.auth.coordinator import ServerConfig, OAuth2JWTClaims
from labgrid.remote.auth.coordinator.jwt import JWTKeyFetcher
from labgrid.remote.auth.coordinator.oauth2 import OAuth2ServerPluginBase, OAuth2ServerPlugin
from labgrid.remote.identity import ClientIdentity


class AlternativeJWTClaims(BaseModel):
    subject: str


@attrs.frozen
class _TestServerConfig(ServerConfig):
    audience: str
    issuer: str
    jwks_uri: str


@attrs.frozen
class _StaticKeyFetcher(JWTKeyFetcher):
    signing_key: PyJWK

    def __call__(self, jwt: str) -> PyJWK:
        return self.signing_key


def test_oauth2_plugin_supports_alternative_claims_mapping() -> None:
    key = jwk.JWK.generate(  # type: ignore[no-untyped-call]
        kty="RSA", size=2048, alg="RS256", use="sig", kid="12345"
    )

    audience = "alternative-audience"
    issuer = "https://alternative-issuer.example/"
    token = jwt.encode(
        {
            "aud": audience,
            "iss": issuer,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "subject": "alternative-user",
        },
        key.export_to_pem(private_key=True, password=None),
        headers={"kid": "12345"},
        algorithm="RS256",
    )

    plugin = OAuth2ServerPluginBase(
        config=_TestServerConfig(
            jwks_uri="https://alternative-issuer.example/jwks",
            audience=audience,
            issuer=issuer,
        ),
        claims_type=AlternativeJWTClaims,
        claims_to_clientidentity=lambda claims: ClientIdentity(
            identity_id=f"subject/{claims.subject}",
            capabilities=set(e for e in Capability),
        ),
    )
    plugin.jwt_validator.jwks_key_fetcher = _StaticKeyFetcher(PyJWK.from_dict(key.export_public(as_dict=True)))

    assert plugin.authenticate({"access-token": [token]}) == ClientIdentity(
        identity_id="subject/alternative-user",
        capabilities=set(e for e in Capability),
    )


def test_oauth2_plugin_default_claims_mapping() -> None:
    key = jwk.JWK.generate(  # type: ignore[no-untyped-call]
        kty="RSA", size=2048, alg="RS256", use="sig", kid="12345"
    )

    audience = "default-audience"
    issuer = "https://default-issuer.example/"
    token = jwt.encode(
        {
            "aud": audience,
            "iss": issuer,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "sub": "default-user",
            "roles": ["user"],
        },
        key.export_to_pem(private_key=True, password=None),
        headers={"kid": "12345"},
        algorithm="RS256",
    )

    plugin = OAuth2ServerPlugin(
        config=_TestServerConfig(
            jwks_uri="https://default-issuer.example/jwks",
            audience=audience,
            issuer=issuer,
        )
    )
    plugin.jwt_validator.jwks_key_fetcher = _StaticKeyFetcher(PyJWK.from_dict(key.export_public(as_dict=True)))

    assert plugin.claims_type is OAuth2JWTClaims
    assert plugin.authenticate({"access-token": [token]}) == ClientIdentity(
        identity_id="default-user",
        capabilities=set(e for e in Capability),
    )
