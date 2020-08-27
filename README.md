# Bonnette

**THIS PROJECT IS UNMAINTAINED**: If you would like to see this properly supported, please make a comment on the issue here https://github.com/jordaneremieff/mangum/issues/86.

ASGI adapter for Azure Functions.

<a href="https://pypi.org/project/bonnette/">
    <img src="https://badge.fury.io/py/bonnette.svg" alt="Package version">
</a>
<a href="https://travis-ci.org/erm/bonnette">
    <img src="https://travis-ci.org/erm/bonnette.svg?branch=master" alt="Build Status">
</a>

**Requirements**: Python 3.6

## Installation

```shell
pip3 install bonnette
```

## Example

```python
import logging
import azure.functions as func
from bonnette import Bonnette


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/html; charset=utf-8"]],
        }
    )
    await send(
        {"type": "http.response.body", "body": b"<html><h1>Hello, world!</h1></html>"}
    )


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")
    handler = Bonnette(app)
    return handler(req)

```
