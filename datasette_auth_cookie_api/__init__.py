from datasette import hookimpl

from .cookie_api_auth import CookieApiAuth


@hookimpl
def asgi_wrapper(datasette):
    config = datasette.plugin_config("datasette-auth-cookie-api") or {}
    api_url = config["api_url"]
    auth_redirect_url = config["auth_redirect_url"]
    original_cookies = config["original_cookies"]

    # require_auth defaults to True unless set otherwise
    require_auth = True
    if require_auth in config:
        require_auth = config["require_auth"]

    def wrap_with_asgi_auth(app):
        return CookieApiAuth(
            app,
            api_url=api_url,
            auth_redirect_url=auth_redirect_url,
            original_cookies=original_cookies,
            require_auth=require_auth,
            # TODO: Fix this security hole:
            cookie_secret='1234',
        )

    return wrap_with_asgi_auth


@hookimpl
def extra_template_vars(request):
    return {"auth": request.scope.get("auth")}
