from urllib.parse import quote
import json
import httpx
import pytest

from itsdangerous import URLSafeSerializer

from datasette_auth_existing_cookies.existing_cookies_auth import ExistingCookiesAuth
from datasette_auth_existing_cookies import asgi_wrapper


class ExistingCookiesAuthTest(ExistingCookiesAuth):
    mock_api_json = {}

    async def json_from_api_for_cookies(self, cookies, host):
        assert "demo.example.com" == host
        return self.mock_api_json


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/", "/fixtures", "/foo/bar"])
@pytest.mark.parametrize("next_secret", [None, "secret"])
async def test_redirects_to_login_page(next_secret, path):
    auth_app = ExistingCookiesAuthTest(
        hello_world_app,
        api_url="https://api.example.com/user-from-cookie",
        auth_redirect_url="https://www.example.com/login",
        original_cookies=("sessionid",),
        cookie_secret="foo",
        cookie_ttl=10,
        require_auth=True,
        next_secret=next_secret,
    )
    async with httpx.AsyncClient(app=auth_app) as client:
        response = await client.get(
            "https://demo.example.com{}".format(path), allow_redirects=False
        )
        assert 302 == response.status_code
        location = response.headers["location"]
        if next_secret is not None:
            signer = URLSafeSerializer(next_secret)
            next_param = "?next_sig=" + quote(
                signer.dumps("https://demo.example.com{}".format(path))
            )
        else:
            next_param = "?next=" + quote("https://demo.example.com{}".format(path))
        assert "https://www.example.com/login{}".format(next_param) == location


@pytest.mark.asyncio
async def test_allow_access_if_auth_is_returned():
    auth_app = ExistingCookiesAuthTest(
        hello_world_app,
        api_url="https://api.example.com/user-from-cookie",
        auth_redirect_url="https://www.example.com/login",
        original_cookies=("sessionid",),
        cookie_secret="foo",
        cookie_ttl=10,
        require_auth=True,
    )
    auth_app.mock_api_json = {"id": 1, "name": "Simon"}
    async with httpx.AsyncClient(app=auth_app) as client:
        response = await client.get("https://demo.example.com/", allow_redirects=False)
        assert 200 == response.status_code
        # It should set a cookie
        api_auth = response.cookies["_api_auth"]
        signer = URLSafeSerializer(auth_app.cookie_secret, "auth-cookie")
        info = signer.loads(api_auth)
        assert {"id", "name", "ts", "verify_hash"} == set(info.keys())
        assert 1 == info["id"]
        assert "Simon" == info["name"]


class FakeDatasette:
    def __init__(self, config):
        self.config = config

    def plugin_config(self, name):
        assert "datasette-auth-existing-cookies" == name
        return self.config


def test_asgi_wrapper():
    app = object()
    config = {
        "api_url": "API-URL",
        "auth_redirect_url": "auth_redirect_url",
        "original_cookies": "original_cookies",
        "cookie_ttl": 20,
        "cookie_secret": "secret",
    }
    wrapper = asgi_wrapper(FakeDatasette(config))
    wrapped = wrapper(app)
    assert config.items() <= wrapped.__dict__.items()
    assert app == wrapped.app


async def hello_world_app(scope, receive, send):
    assert scope["type"] == "http"
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                [b"content-type", b"text/html; charset=UTF-8"],
                [b"cache-control", b"max-age=123"],
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": json.dumps({"hello": "world", "auth": scope.get("auth")}).encode(
                "utf8"
            ),
        }
    )
