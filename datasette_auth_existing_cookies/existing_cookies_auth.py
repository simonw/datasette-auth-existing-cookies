import fnmatch
import hashlib
import hmac
import httpx
import json
import time
from html import escape
from http.cookies import SimpleCookie
from urllib.parse import parse_qsl, urlencode, quote

from itsdangerous import URLSafeSerializer, BadSignature

from .utils import force_list, send_html, cookies_from_scope, url_from_scope


class ExistingCookiesAuth:
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
        next_secret=None,
        trust_x_forwarded_proto=False,
        headers_to_forward=None,
    ):
        self.app = app
        self.api_url = api_url
        self.auth_redirect_url = auth_redirect_url
        self.original_cookies = original_cookies
        self.cookie_secret = cookie_secret
        self.cookie_ttl = cookie_ttl
        self.require_auth = require_auth
        self.next_secret = next_secret
        self.trust_x_forwarded_proto = trust_x_forwarded_proto
        self.headers_to_forward = headers_to_forward or []

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
        if "auth" in scope:
            return scope["auth"]
        cookies = cookies_from_scope(scope)
        auth_cookie = cookies.get(self.cookie_name)
        if not auth_cookie:
            return None
        # Decode the signed cookie
        signer = URLSafeSerializer(self.cookie_secret, "auth-cookie")
        try:
            decoded = signer.loads(auth_cookie)
        except BadSignature:
            return None
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
        _, cookie_hash = self.original_cookies_and_hash(scope)
        if not hmac.compare_digest(verify_hash, cookie_hash):
            return None
        # Passed all the tests, return the decoded auth cookie
        return decoded

    async def json_from_api_for_cookies(self, cookies, headers=None):
        headers = headers or {}
        api_url = self.api_url + "?" + urlencode(headers)
        response = await httpx.AsyncClient().get(api_url, cookies=cookies)
        return response.json()

    def build_auth_redirect(self, next_url):
        if self.next_secret:
            signer = URLSafeSerializer(self.next_secret)
            redirect_param = "?next_sig=" + quote(signer.dumps(next_url))
        else:
            redirect_param = "?next=" + quote(next_url)
        return self.auth_redirect_url + redirect_param

    async def handle_missing_auth(self, scope, receive, send):
        # We authenticate the user by forwarding their cookies
        # on to the configured API endpoint and seeing what
        # we get back.
        original_cookies, cookie_hash = self.original_cookies_and_hash(scope)
        headers = {}
        header_dict = dict(scope["headers"])
        for header in self.headers_to_forward:
            value = header_dict.get(header.encode("utf8"), b"").decode("utf8")
            if value:
                headers[header] = value
        auth = await self.json_from_api_for_cookies(original_cookies, headers)
        # If auth is not '{}' set cookie and forward request
        if auth:
            # ... unless it's a {"forbidden": reason}
            if "forbidden" in auth:
                return await self.access_forbidden(
                    scope, receive, send, auth["forbidden"]
                )
            signer = URLSafeSerializer(self.cookie_secret, "auth-cookie")
            signed_cookie = signer.dumps(
                dict(auth, ts=int(time.time()), verify_hash=cookie_hash)
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
            redirect_url = self.build_auth_redirect(
                url_from_scope(
                    scope, trust_x_forwarded_proto=self.trust_x_forwarded_proto
                )
            )
            await send_html(send, "", 302, [["location", redirect_url]])

    async def access_forbidden(self, scope, receive, send, reason):
        html = """
            <html>
            <head><title>Access Forbidden</title>
            <style>body { font-family: sans-serif; padding: 2em; }</style>
            </head>
            <body><h1>Access Forbidden</h1>
            <p>%s</p></body>
            </html>
        """ % escape(
            reason
        )
        await send_html(send, html, 403)
