# datasette-auth-existing-cookies

[![PyPI](https://img.shields.io/pypi/v/datasette-auth-existing-cookies.svg)](https://pypi.org/project/datasette-auth-existing-cookies/)
[![Changelog](https://img.shields.io/github/v/release/simonw/datasette-auth-existing-cookies?include_prereleases&label=changelog)](https://github.com/simonw/datasette-auth-existing-cookies/releases)
[![Tests](https://github.com/simonw/datasette-auth-existing-cookies/workflows/Test/badge.svg)](https://github.com/simonw/datasette-auth-existing-cookies/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/simonw/datasette-auth-existing-cookies/blob/master/LICENSE)

Datasette plugin that authenticates users based on existing domain cookies.

## When to use this

This plugin allows you to build custom authentication for Datasette when you are hosting a Datasette instance on the same domain as another, authenticated website.

Consider a website on `www.example.com` which supports user authentication.

You could run Datasette on `data.example.com` in a way that lets it see cookies that were set for the `.example.com` domain.

Using this plugin, you could build an API endpoint at `www.example.com/user-for-cookies` which returns a JSON object representing the currently signed-in user, based on their cookies.

The plugin can protect any hits to any `data.example.com` pages by passing their cookies through to that API and seeing if the user should be logged in or not.

You can also use subclassing to decode existing cookies using some other mechanism.

## Configuration

This plugin requires some configuration in the Datasette [metadata.json file](https://datasette.readthedocs.io/en/stable/plugins.html#plugin-configuration).

It needs to know the following:

* Which domain cookies should it be paying attention to? If you are authenticating against Dango this is probably `["sessionid"]`.
* What's an API it can send the incoming cookies to that will decipher them into some user information?
* Where should it redirect the user if they need to sign in?

Example configuration setting all three of these values looks like this:

```json
{
    "plugins": {
        "datasette-auth-existing-cookies": {
            "api_url": "http://www.example.com/user-from-cookies",
            "auth_redirect_url": "http://www.example.com/login",
            "original_cookies": ["sessionid"]
        }
    }
}
```

With this configuration the user's current `sessionid` cookie will be passed to the API URL, as a regular cookie header.

You can use the `"headers_to_forward"` configuration option to specify a list of additional headers from the request that should be forwarded on to the `api_url` as querystring parameters. For example, if you add this to the above configuration:

```json
            "headers_to_forward": ["host", "x-forwarded-for"]
```

Then a hit to `https://data.example.com/` would make the following API call:

    http://www.example.com/user-from-cookies?host=data.example.com&x-forwarded-for=64.18.15.255

The API URL should then return either an empty JSON object if the user is not currently signed in:

```json
{}
```

Or a JSON object representing the user if they ARE signed in:

```json
{
    "id": 123,
    "username": "simonw"
}
```

This object can contain any keys that you like - the information will be stored in a new signed cookie and made available to Datasette code as the `"auth"` dictionary on the ASGI `scope`.

I suggest including at least an `id` and a `username`.

## Templates

You probably want your user's to be able to see that they are signed in. The plugin makes the `auth` data from above directly available within Datasette's templates. You could use a custom `base.html` template (see [template documentation](https://datasette.readthedocs.io/en/stable/custom_templates.html#custom-templates)) that looks like this:

```html+django
{% extends "default:base.html" %}

{% block extra_head %}
<style type="text/css">
.hd .logout {
    float: right;
    text-align: right;
    padding-left: 1em;
}
</style>
{% endblock %}

{% block nav %}
    {{ super() }}
    {% if auth and auth.username %}
        <p class="logout">
            <strong>{{ auth.username }}</strong> &middot; <a href="https://www.example.com/logout">Log out</a>
        </p>
    {% endif %}
{% endblock %}
```

## Other options

- `require_auth`. This defaults to `True`. You can set it to `False` if you want unauthenticated users to be able to view the Datasette instance.
- `cookie_secret`. You can use this to set the signing secret that will be used for the cookie set by this plugin (you should use [secret configuration values](https://datasette.readthedocs.io/en/stable/plugins.html#secret-configuration-values) for this). If you do not set a secret the plugin will use `DATASETTE_SECRET` - though be warned that this may change on each deploy using `datasette publish` if you have not explicitly set it.
- `cookie_ttl`. The plugin sets its own cookie to avoid hitting the backend API for every incoming request. By default it still hits the API at most every 10 seconds, in case the user has signed out on the main site. You can raise or lower the timeout using this setting.
- `trust_x_forwarded_proto`. If you are running behind a proxy that adds HTTPS support for you, you may find that the plugin incorrectly constructs `?next=` URLs with the incorrect scheme. If you know your proxy sends the `x-forwarded-proto` header (you can investigate this with the [datasette-debug-asgi](https://github.com/simonw/datasette-debug-asgi) plugin) setting the `trust_x_forwarded_proto` option to True will cause the plugin to trust that header.
- `next_secret`. See below.

## Login redirect mechanism

If the user does not have a valid authentication cookie they will be redirected to an existing login page.

This page is specified using the `auth_redirect_url` setting.

Given the above example configuration, the URL that the user should be sent to after they log in will be specified as the `?next=` parameter to that page, for example:

    http://www.example.com/login?next=http://foo.example.com/

It is up to you to program the login endpoint such that it is not vulnerable to an [Unvalidated redirect vulnerability](https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html).

One way to do this is by verifying that the URL passed to `?next=` is a URL that belongs to a trusted website. Django's own login view [does this](https://github.com/django/django/blob/50cf183d219face91822c75fa0a15fe2fe3cb32d/django/contrib/auth/views.py#L69-L80) by verifying that the URL hostname is on an approved list.

Another way to do this is to use the `next_secret` configuration parameter to set a signing secret for that URL. This signing secret will be used to construct a `?next_sig=` signed token using the Python [itsdangerous](https://pythonhosted.org/itsdangerous/) module, like this:

    ?next_sig=Imh0dHBzOi8vZGVtby5leGFtcGxlLmNvbS9mb28vYmFyIg.7JdhRCoP7Ow1cRF1ZVengC-qk6c

You should use Datasette's [secret configuration values](https://datasette.readthedocs.io/en/stable/plugins.html#secret-configuration-values) mechanism to set this secret from an environment variable, like so:

    {
        "plugins": {
            "datasette-auth-existing-cookies": {
                "api_url": "http://www.example.com/user-from-cookies",
                "auth_redirect_url": "http://www.example.com/login",
                "original_cookies": ["sessionid"],
                "next_secret":  {
                    "$env": "NEXT_SECRET"
                }
            }
        }
    }

You can verify this secret in Python code for your own login form like so:

```python
from itsdangerous import URLSafeSerializer, BadSignature

def verify_next_sig(next_sig):
    signer = URLSafeSerializer(next_secret)
    try:
        decoded = signer.loads(next_sig)
        return True
    except BadSignature:
        return False
```

If you want to roll your own signing mechanism here you can do so by subclassing `ExistingCookiesAuth` and over-riding the `build_auth_redirect(next_url)` method.

## Permissions

If the current user is signed in but should not have permission to access the Datasette instance, you can indicate so by having the API return the following:

```json
{
    "forbidden": "You do not have permission to access this page."
}
```

The key must be `"forbidden"`. The value can be any string - it will be displayed to the user.

This is particularly useful when handling multiple different subdomains. You may get an API call to the following:

    http://www.example.com/user-from-cookies?host=a-team.example.com

You can check if the authenticated user (based on their cookies) has permission to access to the `a-team` Datasette instance, and return a `"forbidden"` JSON object if they should not be able to view it.

If a user is allowed to access Datasette (because the API returned their user identity as JSON), the plugin will set a cookie on that subdomain granting them access.

This cookie defaults to expiring after ten seconds. This means that if a user has permission removed for any reason they will still have up to ten seconds in which they will be able to continue accessing Datasette. If this is not acceptable to you the `cookie_ttl` setting can be used to reduce this timeout, at the expense of incurring more frequent API calls to check user permissions.
