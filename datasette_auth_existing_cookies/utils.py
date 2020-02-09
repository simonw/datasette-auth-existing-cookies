from http.cookies import SimpleCookie
import json


async def send_html(send, html, status=200, headers=None):
    headers = headers or []
    if "content-type" not in [h.lower() for h, v in headers]:
        headers.append(["content-type", "text/html; charset=UTF-8"])
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                [key.encode("utf8"), value.encode("utf8")] for key, value in headers
            ],
        }
    )
    await send({"type": "http.response.body", "body": html.encode("utf8")})


class Response:
    "Wrapper class making HTTP responses easier to work with"

    def __init__(self, status_code, headers, body):
        self.status_code = status_code
        self.headers = headers
        self.body = body

    def json(self):
        return json.loads(self.text)

    @property
    def text(self):
        # Should decode according to Content-Type, for the moment assumes utf8
        return self.body.decode("utf-8")


def ensure_bytes(s):
    if not isinstance(s, bytes):
        return s.encode("utf-8")
    else:
        return s


def force_list(value):
    if isinstance(value, str):
        return [value]
    return value


def cookies_from_scope(scope):
    cookie = dict(scope.get("headers") or {}).get(b"cookie")
    if not cookie:
        return {}
    simple_cookie = SimpleCookie()
    simple_cookie.load(cookie.decode("utf8"))
    return {key: morsel.value for key, morsel in simple_cookie.items()}


def url_from_scope(scope, trust_x_forwarded_proto=False):
    scheme = scope["scheme"].encode("utf8")
    headers = dict(scope["headers"])
    path = scope.get("raw_path", scope["path"].encode("utf8"))
    host = headers[b"host"]
    if trust_x_forwarded_proto and headers.get(b"x-forwarded-proto"):
        scheme = headers[b"x-forwarded-proto"]
    return (b"%s://%s%s" % (scheme, host, path)).decode("utf8")
