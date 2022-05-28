from asgiref.testing import ApplicationCommunicator
from urllib.parse import quote
import json
import httpx
import pytest

from itsdangerous import URLSafeSerializer

from datasette_auth_existing_cookies.existing_cookies_auth import ExistingCookiesAuth
from datasette_auth_existing_cookies import asgi_wrapper


class ExistingCookiesAuthTest(ExistingCookiesAuth):
    mock_api_json = {}
    expected_headers = {}
    called = False

    async def json_from_api_for_cookies(self, cookies, headers=None):
        self.called = True
        assert self.expected_headers == headers
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
        trust_x_forwarded_proto=False,
    )
    async with httpx.AsyncClient(app=auth_app) as client:
        response = await client.get("https://demo.example.com{}".format(path))
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
@pytest.mark.parametrize("trust_it", [True, False])
async def test_redirects_to_login_page_trusting_x_forwarded_proto(trust_it):
    auth_app = ExistingCookiesAuthTest(
        hello_world_app,
        api_url="https://api.example.com/user-from-cookie",
        auth_redirect_url="https://www.example.com/login",
        original_cookies=("sessionid",),
        cookie_secret="foo",
        cookie_ttl=10,
        require_auth=True,
        trust_x_forwarded_proto=trust_it,
    )
    async with httpx.AsyncClient(app=auth_app) as client:
        url = "http://demo.example.com/"
        headers = {"x-forwarded-proto": "https"}
        response = await client.get(
            url,
            headers=headers,
        )
        assert 302 == response.status_code
        location = response.headers["location"]
        expected = "https://www.example.com/login?next={}".format(
            quote("PROTO://demo.example.com/")
        )
        if trust_it:
            assert expected.replace("PROTO", "https") == location

        else:
            assert expected.replace("PROTO", "http") == location


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
        response = await client.get("https://demo.example.com/")
        assert 200 == response.status_code
        # It should set a cookie
        api_auth = response.cookies["_api_auth"]
        signer = URLSafeSerializer(auth_app.cookie_secret, "auth-cookie")
        info = signer.loads(api_auth)
        assert {"id", "name", "ts", "verify_hash"} == set(info.keys())
        assert 1 == info["id"]
        assert "Simon" == info["name"]


@pytest.mark.asyncio
async def test_access_denied():
    auth_app = ExistingCookiesAuthTest(
        hello_world_app,
        api_url="https://api.example.com/user-from-cookie",
        auth_redirect_url="https://www.example.com/login",
        original_cookies=("sessionid",),
        cookie_secret="foo",
        cookie_ttl=10,
        require_auth=True,
    )
    auth_app.mock_api_json = {"forbidden": "Access not allowed"}
    assert not auth_app.called
    async with httpx.AsyncClient(app=auth_app) as client:
        response = await client.get("https://demo.example.com/")
        assert 403 == response.status_code
        assert "Access not allowed" in response.text
        assert auth_app.called


@pytest.mark.asyncio
async def test_headers_to_forward():
    auth_app = ExistingCookiesAuthTest(
        hello_world_app,
        api_url="https://api.example.com/user-from-cookie",
        auth_redirect_url="https://www.example.com/login",
        original_cookies=("sessionid",),
        cookie_secret="foo",
        cookie_ttl=10,
        require_auth=True,
        headers_to_forward=["host", "accept-encoding"],
    )
    auth_app.mock_api_json = {"id": 1, "name": "Simon"}
    auth_app.expected_headers = {
        "host": "demo.example.com",
        "accept-encoding": "gzip, deflate",
    }
    assert not auth_app.called
    async with httpx.AsyncClient(app=auth_app) as client:
        response = await client.get("https://demo.example.com/")
        assert 200 == response.status_code
        assert auth_app.called


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


@pytest.mark.asyncio
async def test_scope_auth_allows_access():
    # This test can't use httpx because I need a custom scope
    scope = {
        "type": "http",
        "http_version": "1.0",
        "method": "GET",
        "path": "/",
        "headers": [],
    }
    auth_app = ExistingCookiesAuthTest(
        hello_world_app,
        api_url="https://api.example.com/user-from-cookie",
        auth_redirect_url="https://www.example.com/login",
        original_cookies=("sessionid",),
        cookie_secret="foo",
        cookie_ttl=10,
        require_auth=True,
    )
    auth_app.mock_api_json = {"forbidden": "Access not allowed"}
    # With un-authed scope, it should deny
    instance = ApplicationCommunicator(auth_app, scope)
    await instance.send_input({"type": "http.request"})
    output = await instance.receive_output(1)
    assert 403 == output["status"]
    # with authed scope it should 200
    instance = ApplicationCommunicator(
        auth_app, dict(scope, auth={"id": 1, "name": "authed"})
    )
    await instance.send_input({"type": "http.request"})
    output = await instance.receive_output(1)
    assert 200 == output["status"]
