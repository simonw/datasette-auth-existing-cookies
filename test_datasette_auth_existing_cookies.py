from urllib.parse import quote
import pytest
from asgiref.testing import ApplicationCommunicator

from itsdangerous import URLSafeSerializer

from datasette_auth_existing_cookies.existing_cookies_auth import ExistingCookiesAuth


class ExistingCookiesAuthTest(ExistingCookiesAuth):
    mock_api_json = {}

    async def json_from_api_for_cookies(self, cookies):
        return self.mock_api_json


@pytest.fixture
def auth_app():
    return ExistingCookiesAuthTest(
        hello_world_app,
        api_url="https://api.example.com/user-from-cookie",
        auth_redirect_url="https://www.example.com/login",
        original_cookies=("sessionid",),
        cookie_secret="foo",
        cookie_ttl=10,
        require_auth=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/", "/fixtures", "/foo/bar"])
async def test_redirects_to_login_page(path, auth_app):
    instance = ApplicationCommunicator(
        auth_app,
        {
            "type": "http",
            "scheme": "https",
            "http_version": "1.0",
            "method": "GET",
            "path": path,
            "headers": [[b"host", b"demo.example.com"]],
        },
    )
    await instance.send_input({"type": "http.request"})
    output = await instance.receive_output(1)
    assert "http.response.start" == output["type"]
    assert 302 == output["status"]
    headers = tuple([tuple(pair) for pair in output["headers"]])
    signer = URLSafeSerializer(auth_app.cookie_secret, "login-redirect")
    next_sig = quote(signer.dumps("https://demo.example.com{}".format(path)))
    assert (
        b"location",
        ("https://www.example.com/login?next_sig={}".format(next_sig)).encode("utf8"),
    ) in headers
    assert (b"cache-control", b"private") in headers
    assert (await instance.receive_output(1)) == {
        "type": "http.response.body",
        "body": b"",
    }


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
