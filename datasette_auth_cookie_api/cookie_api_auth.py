import fnmatch
import hashlib
import hmac
import httpx
import json
import time
from http.cookies import SimpleCookie
from urllib.parse import parse_qsl, urlencode, quote

from .utils import (
    BadSignature,
    Signer,
    force_list,
    send_html,
    cookies_from_scope,
    url_from_scope,
)


class CookieApiAuth:
    redirect_path_blacklist = ["/favicon.ico", "/-/static/*", "/-/static-plugins/*"]
    cacheable_prefixes = ["/-/static/", "/-/static-plugins/"]
    cookie_name = "_api_auth"

    def __init__(
        self,
        app,
        api_url,
        auth_redirect_url,
        original_cookies,
        cookie_secret,
        cookie_ttl=10,
        require_auth=False,
    ):
        self.app = app
        self.api_url = api_url
        self.auth_redirect_url = auth_redirect_url
        self.original_cookies = original_cookies
        self.cookie_ttl = cookie_ttl
        self.require_auth = require_auth
        self.cookie_secret = cookie_secret

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        send = self.wrapped_send(send, scope)
        auth = self.auth_from_scope(scope)
        if auth or (not self.require_auth):
            await self.app(dict(scope, auth=auth), receive, send)
        else:
            await self.handle_missing_auth(scope, receive, send)

    def wrapped_send(self, send, scope, set_cookies=None):
        async def wrapped_send(event):
            # We only wrap http.response.start with headers
            if not (event["type"] == "http.response.start" and event.get("headers")):
                await send(event)
                return
            # Rebuild headers to include cache-control: private
            path = scope.get("path")
            original_headers = event.get("headers") or []
            if any(path.startswith(prefix) for prefix in self.cacheable_prefixes):
                await send(event)
            else:
                new_headers = [
                    [key, value]
                    for key, value in original_headers
                    if key.lower() != b"cache-control"
                ]
                new_headers.append([b"cache-control", b"private"])
                # Any cookies to set?
                for key, value in (set_cookies or {}).items():
                    cookie = SimpleCookie()
                    cookie[key] = value
                    cookie[key]["path"] = "/"
                    new_headers.append(
                        [
                            b"set-cookie",
                            cookie.output(header="").lstrip().encode("utf8"),
                        ]
                    )

                await send({**event, **{"headers": new_headers}})

        return wrapped_send

    def original_cookies_and_hash(self, scope):
        cookies = cookies_from_scope(scope)
        original_cookies = {
            cookie: cookies.get(cookie) for cookie in self.original_cookies
        }
        cookie_hash = hashlib.md5(
            json.dumps(original_cookies, sort_keys=True).encode("utf8")
        ).hexdigest()
        return original_cookies, cookie_hash

    def auth_from_scope(self, scope):
        cookies = cookies_from_scope(scope)
        auth_cookie = cookies.get(self.cookie_name)
        if not auth_cookie:
            return None
        # Decode the signed cookie
        signer = Signer(self.cookie_secret)
        try:
            cookie_value = signer.unsign(auth_cookie)
        except BadSignature:
            return None
        decoded = json.loads(cookie_value)
        # Has the cookie expired?
        if self.cookie_ttl is not None:
            if "ts" not in decoded:
                return None
            if (int(time.time()) - self.cookie_ttl) > decoded["ts"]:
                return None
        # Check that our cookie's other_hash matches the MD5 of the
        # original cookies
        verify_hash = decoded.get("verify_hash")
        if verify_hash is None:
            return None
        original_cookies, cookie_hash = self.original_cookies_and_hash(scope)
        if not hmac.compare_digest(verify_hash, cookie_hash):
            return None
        # Passed all the tests, return the decoded auth cookie
        return decoded

    async def handle_missing_auth(self, scope, receive, send):
        # We authenticate the user by forwarding their cookies
        # on to the configured API endpoint and seeing what
        # we get back.
        original_cookies, cookie_hash = self.original_cookies_and_hash(scope)
        response = await httpx.AsyncClient().get(self.api_url, cookies=original_cookies)
        auth = response.json()
        # If auth is not '{}' set cookie and forward request
        if auth:
            signer = Signer(self.cookie_secret)
            signed_cookie = signer.sign(
                json.dumps(
                    dict(auth, ts=int(time.time()), verify_hash=cookie_hash),
                    separators=(",", ":"),
                )
            )
            await self.app(
                dict(scope, auth=auth),
                receive,
                self.wrapped_send(
                    send, scope, set_cookies={self.cookie_name: signed_cookie}
                ),
            )
        else:
            # Redirect user to the login page
            signer = Signer(self.cookie_secret)
            signed_redirect = signer.sign(url_from_scope(scope))
            await send_html(
                send,
                "",
                302,
                [
                    [
                        "location",
                        self.auth_redirect_url + "?next_sig=" + quote(signed_redirect),
                    ]
                ],
            )
