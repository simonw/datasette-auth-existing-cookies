# datasette-auth-existing-cookies

[![PyPI](https://img.shields.io/pypi/v/datasette-auth-existing-cookies.svg)](https://pypi.org/project/datasette-auth-existing-cookies/)
[![CircleCI](https://circleci.com/gh/simonw/datasette-auth-existing-cookies.svg?style=svg)](https://circleci.com/gh/simonw/datasette-auth-existing-cookies)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://google.com/simonw/datasette-auth-existing-cookies/blob/master/LICENSE)

Datasette plugin that authenticates users based on existing domain cookies.

**STATUS: Work in progress**. This is currently insecure. Do not use it.

## When to use this

This plugin allows you to build custom authentication for Datasette when you are hosting a Datasette instance on the same domain as another, authenticated website.

Consider a website on `www.example.com` which supports user authentication.

You could run Datasette on `data.example.com` in a way that lets it see cookies that were set for the `.example.com` domain.

Using this plugin, you could build an API endpoint at `www.example.com/user-for-cookies` which returns a JSON object representing the currently signed-in user, based on their cookies.

The plugin can protect any hits to any `data.example.com` pages by passing their cookies through to that API and seeing if the user should be logged in or not.

You can also use subclassing to decode existing cookies using some other mechanism.
