# datasette-auth-existing-cookies

[![PyPI](https://img.shields.io/pypi/v/datasette-auth-existing-cookies.svg)](https://pypi.org/project/datasette-auth-existing-cookies/)
[![CircleCI](https://circleci.com/gh/simonw/datasette-auth-existing-cookies.svg?style=svg)](https://circleci.com/gh/simonw/datasette-auth-existing-cookies)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://google.com/simonw/datasette-auth-existing-cookies/blob/master/LICENSE)

Datasette plugin that authenticates users based on existing domain cookies.

**STATUS: Work in progress**.

## When to use this

This plugin allows you to build custom authentication for Datasette when you are hosting a Datasette instance on the same domain as another, authenticated website.

Consider a website on `www.example.com` which supports user authentication.

You could run Datasette on `data.example.com` in a way that lets it see cookies that were set for the `.example.com` domain.

Using this plugin, you could build an API endpoint at `www.example.com/user-for-cookies` which returns a JSON object representing the currently signed-in user, based on their cookies.

The plugin can protect any hits to any `data.example.com` pages by passing their cookies through to that API and seeing if the user should be logged in or not.

You can also use subclassing to decode existing cookies using some other mechanism.

## Login redirect mechanism

If the user does not have a valid authentication cookie they will be redirected to an existing login page.

This page is specified using the `auth_redirect_url` setting.

For example:

    {
        "plugins": {
            "datasette-auth-existing-cookies": {
                "api_url": "http://www.example.com/user-from-cookies",
                "auth_redirect_url": "http://www.example.com/login",
                "original_cookies": ["sessionid"]
            }
        }
    }

The URL that the user should be sent to after they log in will be specified as the `?next=` parameter to that page, for example:

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
