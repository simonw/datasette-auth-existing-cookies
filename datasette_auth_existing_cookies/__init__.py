from datasette import hookimpl
from cachetools import TTLCache
import httpx


@hookimpl
def actor_from_request(datasette, request):
    config = datasette.plugin_config("datasette-auth-existing-cookies") or {}
    api_url = config.get("api_url")
    if api_url is None:
        return None
    cookies_to_pass = config.get("cookies")
    headers_to_pass = config.get("headers")
    ttl = config.get("ttl")
    if ttl is not None:
        if datasette._auth_existing_cookies_cache is None:
            datasette._auth_existing_cookies_cache = TTLCache(1000, ttl=ttl)
    else:
        datasette._auth_existing_cookies_cache = None

    async def inner():
        if cookies_to_pass:
            cookies = {
                key: request.cookies.get(key)
                for key in cookies_to_pass
                if request.cookies.get(key)
            }
        else:
            # Send them all
            cookies = request.cookies
        header_params = {}
        if headers_to_pass:
            for header in headers_to_pass:
                value = request.headers.get(header.lower())
                if value is not None:
                    header_params[header.lower()] = value

        cache_key = None
        if datasette._auth_existing_cookies_cache is not None:
            # Maybe there's a cached version of this?
            # Cache key is a tuple-of-tuples-of-tuples, (cookies, headers)
            # where cookies and headers are sorted tuples of (key, value) pairs
            cookies_for_key = tuple(sorted(cookies.items()))
            headers_for_key = tuple(sorted(header_params.items()))
            cache_key = (cookies_for_key, headers_for_key)
            if cache_key in datasette._auth_existing_cookies_cache:
                return datasette._auth_existing_cookies_cache[cache_key]

        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, params=header_params, cookies=cookies)

        if response.status_code != 200:
            actor = None
        else:
            actor = response.json()
        if datasette._auth_existing_cookies_cache is not None:
            datasette._auth_existing_cookies_cache[cache_key] = actor
        return actor

    return inner
