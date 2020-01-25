from setuptools import setup
import os

VERSION = "0.1"


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="datasette-auth-cookie-api",
    description="Datasette plugin that authenticates users by passing their cookies to an API",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Simon Willison",
    url="https://github.com/simonw/datasette-auth-cookie-api",
    license="Apache License, Version 2.0",
    version=VERSION,
    packages=["datasette_auth_cookie_api"],
    entry_points={"datasette": ["auth_cookie_api = datasette_auth_cookie_api"]},
    install_requires=["httpx"],
    extras_require={
        "test": ["datasette", "pytest", "pytest-asyncio", "asgiref~=3.1.2"]
    },
    tests_require=["datasette-auth-cookie-api[test]"],
)
