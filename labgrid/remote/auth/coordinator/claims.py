from pydantic import BaseModel, Field


class OAuth2JWTClaims(BaseModel):
    sub: str = Field(description="The identifier for the requestor")
    roles: list[str] = Field(description="Labgrid roles")
