"""Self-hosted OAuth 2.1 for the Sales OS MCP server (Route 1: token-OAuth).

claude.ai (and other Claude apps) will only connect to a custom connector that
is an OAuth provider — they never present a raw-bearer-token field. This wraps
the existing per-tenant access keys (SALES_OS_TOKENS) in a minimal OAuth flow so
onboarding stays "connect + paste your key once":

  1. The client does Dynamic Client Registration + /authorize with PKCE.
  2. authorize() redirects the user to our /consent page, carrying the (signed)
     authorization request so it can't be tampered with.
  3. The user pastes their Sales OS access key. We validate it -> tenant, mint a
     short-lived auth code bound to that tenant (via the code's `subject`), then
     exchange it for a signed-JWT access token whose `subject` is the tenant.
     The MCP tools resolve the tenant from that subject, exactly as before.

Access/refresh tokens are stateless signed JWTs, so a redeploy doesn't sign
everyone out. DCR clients and the signing secret are persisted in SQLite. Auth
codes live in memory (they're valid for minutes and a lost one just re-prompts).

Composed with the existing StaticTokenVerifier via MultiAuth, so raw tenant
tokens still work for non-OAuth clients (Claude Desktop, API, the smoke test).
"""

import html
import secrets
import time

import jwt
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from fastmcp.server.auth.auth import ClientRegistrationOptions, OAuthProvider

import storage

SCOPE = "sales-os"
ACCESS_TTL = 60 * 60            # 1 hour
REFRESH_TTL = 60 * 24 * 60 * 60  # 60 days
CODE_TTL = 5 * 60              # 5 minutes
REQUEST_TTL = 10 * 60          # 10 minutes to complete consent


def _load_secret() -> str:
    """Stable HS256 signing secret, persisted so tokens survive restarts."""
    s = storage.kv_get("oauth_signing_secret")
    if not s:
        s = secrets.token_urlsafe(48)
        storage.kv_set("oauth_signing_secret", s)
    return s


class SalesOsOAuthProvider(OAuthProvider):
    """Minimal OAuth 2.1 server that authenticates a tenant by its access key."""

    def __init__(self, *, base_url: str, tokens: dict[str, str]):
        super().__init__(
            base_url=base_url,
            resource_base_url=base_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]
            ),
        )
        self._issuer = str(base_url).rstrip("/")
        self._tokens = tokens                       # access_key -> tenant
        self._secret = _load_secret()
        self._codes: dict[str, AuthorizationCode] = {}

    # --- token/JWT helpers ---------------------------------------------------

    def _encode(self, claims: dict) -> str:
        return jwt.encode(claims, self._secret, algorithm="HS256")

    def _decode(self, token: str, typ: str | None = None) -> dict | None:
        try:
            claims = jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            return None
        if typ is not None and claims.get("typ") != typ:
            return None
        return claims

    def _issue(self, client_id: str, tenant: str, scopes: list[str]) -> OAuthToken:
        now = int(time.time())
        scopes = scopes or [SCOPE]
        access = self._encode({
            "iss": self._issuer, "sub": tenant, "azp": client_id,
            "scope": scopes, "typ": "access", "iat": now, "exp": now + ACCESS_TTL,
        })
        refresh = self._encode({
            "iss": self._issuer, "sub": tenant, "azp": client_id,
            "scope": scopes, "typ": "refresh", "iat": now, "exp": now + REFRESH_TTL,
        })
        return OAuthToken(
            access_token=access, token_type="Bearer", expires_in=ACCESS_TTL,
            refresh_token=refresh, scope=" ".join(scopes),
        )

    # --- client registration (persisted) ------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        raw = storage.kv_get(f"oauthclient:{client_id}")
        if not raw:
            return None
        try:
            return OAuthClientInformationFull.model_validate_json(raw)
        except ValueError:
            return None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        storage.kv_set(f"oauthclient:{client_info.client_id}", client_info.model_dump_json())

    # --- authorize: hand off to the consent page ----------------------------

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        # redirect_uri is already validated against the client by the framework.
        request_token = self._encode({
            "typ": "authreq",
            "cid": client.client_id,
            "ru": str(params.redirect_uri),
            "rue": params.redirect_uri_provided_explicitly,
            "st": params.state,
            "cc": params.code_challenge,
            "sc": params.scopes or [SCOPE],
            "rs": str(params.resource) if params.resource else None,
            "exp": int(time.time()) + REQUEST_TTL,
        })
        return f"/consent?rt={request_token}"

    # --- authorization codes ------------------------------------------------

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self._codes.get(authorization_code)
        if not code or code.client_id != client.client_id:
            return None
        if code.expires_at < time.time():
            self._codes.pop(authorization_code, None)
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if authorization_code.code not in self._codes:
            raise TokenError("invalid_grant", "Authorization code not found or already used.")
        self._codes.pop(authorization_code.code, None)  # single use
        return self._issue(client.client_id, authorization_code.subject, authorization_code.scopes)

    # --- refresh tokens (stateless JWT) -------------------------------------

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        claims = self._decode(refresh_token, "refresh")
        if not claims or claims.get("azp") != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token, client_id=client.client_id,
            scopes=claims.get("scope", [SCOPE]), expires_at=claims.get("exp"),
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        claims = self._decode(refresh_token.token, "refresh")
        if not claims:
            raise TokenError("invalid_grant", "Invalid refresh token.")
        requested = set(scopes or [])
        if requested and not requested.issubset(set(refresh_token.scopes)):
            raise TokenError("invalid_scope", "Requested scopes exceed the grant.")
        return self._issue(client.client_id, claims["sub"], scopes or refresh_token.scopes)

    # --- access tokens (stateless JWT) --------------------------------------

    async def load_access_token(self, token: str) -> AccessToken | None:
        claims = self._decode(token, "access")
        if not claims:
            return None
        return AccessToken(
            token=token, client_id=claims.get("azp", ""),
            scopes=claims.get("scope", [SCOPE]), expires_at=claims.get("exp"),
            subject=claims.get("sub"),
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        return await self.load_access_token(token)

    async def revoke_token(self, token) -> None:
        # Tokens are stateless JWTs; nothing to delete server-side. (A denylist
        # could be added later if hard revocation before expiry is needed.)
        return None

    # --- consent page (mounted as a custom route by server.py) --------------

    async def handle_consent(self, request: Request) -> HTMLResponse | RedirectResponse:
        if request.method == "GET":
            claims = self._decode(request.query_params.get("rt", ""), "authreq")
            if not claims:
                return HTMLResponse(_page(_EXPIRED), status_code=400)
            return HTMLResponse(_consent_form(request.query_params.get("rt", "")))

        form = await request.form()
        rt = str(form.get("rt", ""))
        key = str(form.get("access_key", "")).strip()
        claims = self._decode(rt, "authreq")
        if not claims:
            return HTMLResponse(_page(_EXPIRED), status_code=400)

        tenant = self._tokens.get(key)
        if not tenant:
            return HTMLResponse(
                _consent_form(rt, error="That access key wasn’t recognised. Check it and try again."),
                status_code=401,
            )

        code = secrets.token_urlsafe(24)
        self._codes[code] = AuthorizationCode(
            code=code, client_id=claims["cid"], redirect_uri=claims["ru"],
            redirect_uri_provided_explicitly=claims["rue"], scopes=claims["sc"],
            expires_at=time.time() + CODE_TTL, code_challenge=claims["cc"],
            subject=tenant, resource=claims.get("rs"),
        )
        return RedirectResponse(
            construct_redirect_uri(claims["ru"], code=code, state=claims.get("st")),
            status_code=302,
        )


# --- consent HTML ------------------------------------------------------------

def _page(body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Connect to Sales OS</title><style>"
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f3f5f8;"
        "color:#24303f;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}"
        ".card{background:#fff;max-width:400px;width:92%;padding:32px 30px;border-radius:14px;"
        "box-shadow:0 10px 40px rgba(20,40,80,.12)}"
        ".brand{font-size:18px;font-weight:700;color:#0b6b53;margin-bottom:6px}"
        "h1{font-size:17px;margin:0 0 6px}p{color:#52616b;font-size:13.5px;line-height:1.5;margin:0 0 18px}"
        "label{display:block;font-size:12px;font-weight:600;color:#52616b;margin-bottom:6px}"
        "input{width:100%;box-sizing:border-box;padding:11px 12px;font-size:14px;border:1px solid #d3dae3;"
        "border-radius:8px;margin-bottom:16px}input:focus{outline:none;border-color:#0b6b53}"
        "button{width:100%;padding:11px;font-size:14px;font-weight:600;color:#fff;background:#0b6b53;"
        "border:none;border-radius:8px;cursor:pointer}button:hover{background:#095843}"
        ".err{background:#fdecec;color:#b3261e;font-size:12.5px;padding:9px 11px;border-radius:7px;margin-bottom:14px}"
        "</style></head><body><div class='card'>" + body + "</div></body></html>"
    )


_EXPIRED = (
    "<div class='brand'>Sales OS</div><h1>This sign-in link expired</h1>"
    "<p>For your security the connection request timed out. Close this window and "
    "reconnect the Sales OS connector to try again.</p>"
)


def _consent_form(rt: str, error: str = "") -> str:
    err = f"<div class='err'>{html.escape(error)}</div>" if error else ""
    body = (
        "<div class='brand'>Sales OS</div>"
        "<h1>Connect your workspace</h1>"
        "<p>Paste the Sales OS access key you were given to connect this account.</p>"
        f"{err}"
        "<form method='post' action='/consent'>"
        f"<input type='hidden' name='rt' value='{html.escape(rt)}'>"
        "<label for='k'>Access key</label>"
        "<input id='k' name='access_key' type='password' autocomplete='off' "
        "autofocus placeholder='Your Sales OS access key'>"
        "<button type='submit'>Connect</button>"
        "</form>"
    )
    return _page(body)
