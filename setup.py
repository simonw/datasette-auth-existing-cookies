from setuptools import setup
import os

VERSION = "0.6"


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="datasette-auth-existing-cookies",
    description="Datasette plugin that authenticates users based on existing domain cookies",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Simon Willison",
    url="https://github.com/simonw/datasette-auth-existing-cookies",
    license="Apache License, Version 2.0",
    version=VERSION,
    python_requires=">=3.6",
    packages=["datasette_auth_existing_cookies"],
    entry_points={
        "datasette": ["auth_existing_cookies = datasette_auth_existing_cookies"]
    },
    install_requires=["appdirs", "httpx", "itsdangerous"],
    extras_require={"test": ["datasette", "pytest", "pytest-asyncio"]},
    tests_require=["datasette-auth-existing-cookies[test]"],
)
