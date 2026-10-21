from typing import Callable, Generic, List, Mapping, Protocol, TypeVar

import attrs
from jwt import DecodeError, ExpiredSignatureError
from pydantic import BaseModel, ValidationError

from labgrid.remote.auth.capability import Capability
from labgrid.remote.auth.coordinator.claims import OAuth2JWTClaims
from labgrid.remote.auth.coordinator.jwt import JWTValidator
from labgrid.remote.auth.coordinator.mapping import RoleMapping
from labgrid.remote.auth.plugin import CoordinatorAuthPlugin, IdentityError
from labgrid.remote.identity import ClientIdentity

OAUTH2_PLUGIN_METADATA_KEY = "access-token"

JWTClaimsT = TypeVar("JWTClaimsT", bound=BaseModel)

DEFAULT_ROLE_MAPPING = RoleMapping(
    {"user": set(e for e in Capability)},
)


def default_claims_to_clientIdentity(claims: OAuth2JWTClaims) -> ClientIdentity:
    capabilities = DEFAULT_ROLE_MAPPING(set(claims.roles))
    return ClientIdentity(identity_id=claims.sub, capabilities=capabilities)


class ServerConfig(Protocol):
    @property
    def jwks_uri(self) -> str: ...

    @property
    def audience(self) -> str: ...

    @property
    def issuer(self) -> str: ...


@attrs.define(eq=False)
class OAuth2ServerPluginBase(CoordinatorAuthPlugin, Generic[JWTClaimsT]):
    config: ServerConfig = attrs.field()
    claims_type: type[JWTClaimsT] = attrs.field()
    claims_to_clientidentity: Callable[[JWTClaimsT], ClientIdentity] = attrs.field()
    metadata_key: str = attrs.field(default=OAUTH2_PLUGIN_METADATA_KEY)
    jwt_validator: JWTValidator[JWTClaimsT] = attrs.field(init=False)

    def __attrs_post_init__(self) -> None:
        self.jwt_validator = JWTValidator(
            jwks_uri=self.config.jwks_uri,
            audience=self.config.audience,
            issuer=self.config.issuer,
            claims_type=self.claims_type,
        )

    def authenticate(self, metadata: Mapping[str, List[str]]) -> ClientIdentity:
        if not metadata:
            raise IdentityError("No metadata provided")

        if self.metadata_key not in metadata or len(metadata[self.metadata_key]) != 1:
            raise IdentityError("Invalid metadata provided")

        try:
            claims = self.jwt_validator(metadata[self.metadata_key][0])
            principal = self.claims_to_clientidentity(claims)

            if not principal.capabilities:
                raise IdentityError("No capabilities")

            return principal
        except ExpiredSignatureError:
            raise IdentityError("Token Expired")
        except (DecodeError, ValidationError):
            raise IdentityError("Invalid Token")


class OAuth2ServerPlugin(OAuth2ServerPluginBase[OAuth2JWTClaims]):
    def __init__(
        self,
        config: ServerConfig,
        claims_to_clientidentity: Callable[[OAuth2JWTClaims], ClientIdentity] = default_claims_to_clientIdentity,
        metadata_key: str = OAUTH2_PLUGIN_METADATA_KEY,
    ) -> None:
        super().__init__(
            config=config,
            claims_type=OAuth2JWTClaims,
            claims_to_clientidentity=claims_to_clientidentity,
            metadata_key=metadata_key,
        )
