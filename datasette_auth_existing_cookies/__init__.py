from datasette import hookimpl
import appdirs
import json
import pathlib
import secrets

from .existing_cookies_auth import ExistingCookiesAuth


@hookimpl(trylast=True)
def asgi_wrapper(datasette):
    config = datasette.plugin_config("datasette-auth-existing-cookies") or {}
    api_url = config["api_url"]
    auth_redirect_url = config["auth_redirect_url"]
    original_cookies = config["original_cookies"]
    cookie_secret = config.get("cookie_secret")
    next_secret = config.get("next_secret")
    cookie_ttl = int(config.get("cookie_ttl") or 10)
    trust_x_forwarded_proto = config.get("trust_x_forwarded_proto") or False
    headers_to_forward = config.get("headers_to_forward") or False
    if cookie_secret is None:
        secrets_path = (
            pathlib.Path(appdirs.user_state_dir("datasette-auth-existing-cookies"))
            / "secrets.json"
        )
        if secrets_path.exists():
            cookie_secret = json.load(secrets_path.open())["secret"]
        else:
            secrets_path.parent.mkdir(exist_ok=True)
            cookie_secret = secrets.token_hex(64)
            secrets_path.write_text(json.dumps({"secret": cookie_secret}))

    # require_auth defaults to True unless set otherwise
    require_auth = True
    if require_auth in config:
        require_auth = config["require_auth"]

    def wrap_with_asgi_auth(app):
        return ExistingCookiesAuth(
            app,
            api_url=api_url,
            auth_redirect_url=auth_redirect_url,
            original_cookies=original_cookies,
            require_auth=require_auth,
            cookie_secret=cookie_secret,
            next_secret=next_secret,
            cookie_ttl=cookie_ttl,
            trust_x_forwarded_proto=trust_x_forwarded_proto,
            headers_to_forward=headers_to_forward,
        )

    return wrap_with_asgi_auth


@hookimpl
def extra_template_vars(request):
    return {"auth": request.scope.get("auth") if request else None}
