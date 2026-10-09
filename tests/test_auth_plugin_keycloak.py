import os
from http.server import BaseHTTPRequestHandler, HTTPServer

import attrs
import pytest
from requests_oauthlib import OAuth2Session

from labgrid.remote.auth.coordinator.oauth2 import OAuth2ServerPlugin, ServerConfig
from labgrid.remote.auth.capability import Capability


CLIENT_ID = "testclient"
REDIRECT_URI = "http://localhost:8901"

pytestmark = pytest.mark.skipif(
    os.environ.get("KEYCLOAK_TEST") != "true",
    reason="Set KEYCLOAK_TEST=true to run the interactive Keycloak test",
)


@attrs.frozen
class _KeycloakConfig(ServerConfig):
    audience: str
    issuer: str
    jwks_uri: str


def _authorization_response(authorization_url: str) -> str:
    callback_urls: list[str] = []

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            callback_urls.append(f"{REDIRECT_URI}{self.path}")
            body = b"Login complete. You can close this browser tab."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    with HTTPServer(("localhost", 8901), CallbackHandler) as callback_server:
        callback_server.timeout = 300
        print(f"Open this URL and log in:\n\n{authorization_url}\n", flush=True)
        callback_server.handle_request()

    if len(callback_urls) != 1:
        raise AssertionError("Keycloak did not return one authorization response")
    return callback_urls[0]


def test_plugin_keycloak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OAUTHLIB_INSECURE_TRANSPORT", "1")

    oauth_session = OAuth2Session(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        pkce="S256",
    )
    authorization_url, _ = oauth_session.authorization_url(
        "http://localhost:8080/realms/demorealm/protocol/openid-connect/auth"
    )
    authorization_response = _authorization_response(authorization_url)

    token = oauth_session.fetch_token(
        "http://localhost:8080/realms/demorealm/protocol/openid-connect/token",
        authorization_response=authorization_response,
        include_client_id=True,
        timeout=10,
    )
    access_token = token.get("access_token")
    if not isinstance(access_token, str):
        raise AssertionError("Keycloak did not return an access token")

    # Print access token for local debugging
    print(access_token)

    plugin = OAuth2ServerPlugin(
        _KeycloakConfig(
            audience=CLIENT_ID,
            issuer="http://localhost:8080/realms/demorealm",
            jwks_uri=(
                "http://localhost:8080/realms/demorealm/protocol/openid-connect/certs"
            ),
        )
    )
    principal = plugin.authenticate({"access-token": [access_token]})

    assert principal.id
    assert principal.capabilities == set(e for e in Capability)
