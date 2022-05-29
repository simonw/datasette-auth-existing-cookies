from datasette.app import Datasette
import pytest


@pytest.fixture
def non_mocked_hosts():
    # This ensures httpx-mock will not affect Datasette's own
    # httpx calls made in the tests by datasette.client:
    return ["localhost"]


@pytest.mark.asyncio
async def test_no_config_does_nothing():
    datasette = Datasette()
    response = await datasette.client.get("/-/actor.json")
    assert response.json() == {"actor": None}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cookies,expected_cookie",
    (
        ({}, None),
        ({"sessionid": "123"}, "sessionid=123"),
        ({"one": "1", "two": "2"}, "one=1; two=2"),
    ),
)
async def test_auth_user_default_passes_cookies(httpx_mock, cookies, expected_cookie):
    httpx_mock.add_response(json={"id": "1", "name": "Trish"})
    datasette = Datasette(
        metadata={
            "plugins": {
                "datasette-auth-existing-cookies": {
                    "api_url": "https://www.example.com/user-from-cookies"
                }
            }
        }
    )
    response = await datasette.client.get("/-/actor.json", cookies=cookies)
    assert response.json() == {"actor": {"id": "1", "name": "Trish"}}
    request = httpx_mock.get_request()
    if expected_cookie:
        assert request.headers["cookie"] == expected_cookie
    else:
        assert "cookie" not in request.headers


@pytest.mark.asyncio
async def test_cookie_configuration(httpx_mock):
    httpx_mock.add_response(json={"id": "1", "name": "Trish"})
    datasette = Datasette(
        metadata={
            "plugins": {
                "datasette-auth-existing-cookies": {
                    "api_url": "https://www.example.com/user-from-cookies",
                    "cookies": ["sessionid"],
                }
            }
        }
    )
    response = await datasette.client.get(
        "/-/actor.json", cookies={"sessionid": "abc", "ignoreme": "1"}
    )
    assert response.json() == {"actor": {"id": "1", "name": "Trish"}}
    request = httpx_mock.get_request()
    assert request.headers["cookie"] == "sessionid=abc"
