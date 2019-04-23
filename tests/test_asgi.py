import typing
import pytest
from bonnette import Bonnette


class MockHttpRequest:
    def __init__(
        self,
        method: str,
        url: str,
        headers: typing.Optional[typing.Mapping[str, str]] = None,
        params: typing.Optional[typing.Mapping[str, str]] = None,
        route_params: typing.Optional[typing.Mapping[str, str]] = None,
        body: bytes = None,
    ) -> None:
        self.method = method
        self.url = url
        self.headers = headers
        self.params = params
        self.route_params = route_params
        self.body = body

    def get_body(self) -> str:
        return self.body


def test_asgi_response() -> None:
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

    mock_request = MockHttpRequest(
        "GET",
        "/",
        headers={"content-type": "text/html; charset=utf-8"},
        params={"name": "val"},
        route_params=None,
        body=None,
    )
    handler = Bonnette(app)
    response = handler(mock_request)

    assert response.status_code == 200
    assert response.get_body() == b"<html><h1>Hello, world!</h1></html>"
    assert response.charset == "utf-8"
    assert response.mimetype == "text/html"


def test_asgi_response_with_body() -> None:
    async def app(scope, receive, send):
        message = await receive()
        body = message["body"]
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/html; charset=utf-8"]],
            }
        )
        await send({"type": "http.response.body", "body": body})

    body = b"123"
    mock_request = MockHttpRequest(
        "POST",
        "/",
        headers={"content-type": "text/html; charset=utf-8"},
        params=None,
        route_params=None,
        body=body,
    )

    handler = Bonnette(app)
    response = handler(mock_request)

    assert response.status_code == 200
    assert response.get_body() == b"123"
    assert response.charset == "utf-8"
    assert response.mimetype == "text/html"


def test_asgi_spec_version() -> None:
    def app(scope):
        async def asgi(receive, send):
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

        return asgi

    mock_request = MockHttpRequest(
        "GET",
        "/",
        headers={"content-type": "text/html; charset=utf-8"},
        params={"name": "val"},
        route_params=None,
        body=None,
    )
    handler = Bonnette(app, spec_version=2)
    response = handler(mock_request)

    assert response.status_code == 200
    assert response.get_body() == b"<html><h1>Hello, world!</h1></html>"
    assert response.charset == "utf-8"
    assert response.mimetype == "text/html"


def test_asgi_cycle_state() -> None:
    async def app(scope, receive, send):
        assert scope["type"] == "http"
        await send({"type": "http.response.body", "body": b"Hello, world!"})

    mock_request = MockHttpRequest(
        "GET",
        "/",
        headers={"content-type": "text/html; charset=utf-8"},
        params={"name": "val"},
        route_params=None,
        body=None,
    )

    with pytest.raises(RuntimeError):
        Bonnette(app)(mock_request)

    async def app(scope, receive, send):
        assert scope["type"] == "http"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.start", "status": 200, "headers": []})

    with pytest.raises(RuntimeError):
        Bonnette(app)(mock_request)
