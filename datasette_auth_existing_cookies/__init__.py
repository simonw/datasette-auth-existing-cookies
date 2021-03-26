from datasette import hookimpl
import httpx


def actor_from_request(datasette, request):
    async def inner():
        config = datasette.plugin_config("datasette-auth-existing-cookies") or {}
        api_url = config["api_url"]
        response = await httpx.AsyncClient().get(api_url, cookies=request.cookies)
        actor = response.json()
        if actor:
            return actor
        else:
            return None
    return inner
