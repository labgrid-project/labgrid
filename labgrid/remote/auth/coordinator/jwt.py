from typing import Generic, Protocol, TypeVar

import attrs
from jwt import PyJWK, PyJWKClient, decode
from pydantic import BaseModel


JWTClaimsT = TypeVar("JWTClaimsT", bound=BaseModel)


@attrs.define(eq=False)
class JWKSKeyFetcher:
    jwks_uri: str = attrs.field()
    client: PyJWKClient = attrs.field(init=False)

    def __attrs_post_init__(self) -> None:
        self.client = PyJWKClient(self.jwks_uri)

    def __call__(self, jwt: str) -> PyJWK:
        return self.client.get_signing_key_from_jwt(jwt)


class JWTKeyFetcher(Protocol):
    def __call__(self, jwt: str) -> PyJWK: ...


@attrs.define(eq=False)
class JWTValidator(Generic[JWTClaimsT]):
    jwks_uri: str = attrs.field()
    audience: str = attrs.field()
    issuer: str = attrs.field()
    claims_type: type[JWTClaimsT] = attrs.field()
    jwks_key_fetcher: JWTKeyFetcher = attrs.field(init=False)

    def __attrs_post_init__(self) -> None:
        self.jwks_key_fetcher = JWKSKeyFetcher(self.jwks_uri)

    def __call__(self, jwt: str) -> JWTClaimsT:
        signing_key = self.jwks_key_fetcher(jwt)
        claims_dict = decode(
            jwt,
            signing_key,
            audience=str(self.audience),
            issuer=str(self.issuer),
            options={
                "require": [
                    "exp",
                    "iss",
                    "aud",
                ],
            },
        )
        return self.claims_type.model_validate(claims_dict)
