from datasette import hookimpl
import httpx


@hookimpl
def actor_from_request(datasette, request):
    async def inner():
        config = datasette.plugin_config("datasette-auth-existing-cookies") or {}
        api_url = config.get("api_url")
        if api_url is None:
            return None
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, cookies=request.cookies)
        if response.status_code != 200:
            return None
        actor = response.json()
        if actor:
            return actor
        else:
            return None

    return inner
