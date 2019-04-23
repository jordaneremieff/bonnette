# Bonnette

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

Bonnette consists of a single adapter class for using ASGI applications on Azure Functions.

```python
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
        {
            "type": "http.response.body",
            "body": b"<html><h1>Hello, world!</h1></html>",
        }
    )

handler = Bonnette(app)
```

## Dependencies

`azure-functions` - *required* for Azure Function support.
