# datasette-auth-cookie-api

[![PyPI](https://img.shields.io/pypi/v/datasette-auth-cookie-api.svg)](https://pypi.org/project/datasette-auth-cookie-api/)
[![CircleCI](https://circleci.com/gh/simonw/datasette-auth-cookie-api.svg?style=svg)](https://circleci.com/gh/simonw/datasette-auth-cookie-api)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://google.com/simonw/datasette-auth-cookie-api/blob/master/LICENSE)

Datasette plugin that authenticates users by passing their cookies to an external API.

**STATUS: Work in progress**. This is currently insecure. Do not use it.

## When to use this

This plugin allows you to build custom authentication for Datasette when you are hosting a Datasette instance on the same domain as another, authenticated website.

Consider a website on `www.example.com` which supports user authentication.

You could run Datasette on `data.example.com` in a way that lets it see cookies that were set for the `.example.com` domain.

Using this plugin, you could build an API endpoint at `www.example.com/user-for-cookies` which returns a JSON object representing the currently signed-in user, based on their cookies.

The plugin can protect any hits to any `data.example.com` pages by passing their cookies through to that API and seeing if the user should be logged in or not.
