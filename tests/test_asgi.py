import pytest

from starlette.applications import Starlette
from starlette.responses import HTMLResponse

from bonnette import Bonnette


def test_asgi_scope(mock_http_request) -> None:
    request = mock_http_request()
    expected_scope = {
        "client": None,
        "headers": [[b"content-type", b"text/html; charset=utf-8"]],
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "raw_path": None,
        "scheme": "",
        "server": None,
        "type": "http",
    }

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

        assert scope == expected_scope

    handler = Bonnette(app, enable_lifespan=False)
    response = handler(request)

    assert response.status_code == 200
    assert response.get_body() == b"<html><h1>Hello, world!</h1></html>"
    assert response.charset == "utf-8"
    assert response.mimetype == "text/html"


def test_asgi_response_with_body(mock_http_request) -> None:
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
    request = mock_http_request(method="POST", body=body)
    handler = Bonnette(app)
    response = handler(request)

    assert response.status_code == 200
    assert response.get_body() == b"123"
    assert response.charset == "utf-8"
    assert response.mimetype == "text/html"


def test_asgi_cycle_state(mock_http_request) -> None:
    request = mock_http_request(params={"name": "val"})

    async def app(scope, receive, send):
        assert scope["type"] == "http"
        await send({"type": "http.response.body", "body": b"Hello, world!"})

    with pytest.raises(RuntimeError):
        handler = Bonnette(app, enable_lifespan=False)
        handler(request)

    async def app(scope, receive, send):
        assert scope["type"] == "http"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.start", "status": 200, "headers": []})

    with pytest.raises(RuntimeError):
        handler = Bonnette(app, enable_lifespan=False)
        handler(request)


def test_starlette_response(mock_http_request) -> None:
    request = mock_http_request()
    startup_complete = False
    shutdown_complete = False

    app = Starlette()

    @app.on_event("startup")
    async def on_startup():
        nonlocal startup_complete
        startup_complete = True

    @app.on_event("shutdown")
    async def on_shutdown():
        nonlocal shutdown_complete
        shutdown_complete = True

    @app.route("/")
    def homepage(request):
        return HTMLResponse("<html><h1>Hello, world!</h1></html>")

    assert not startup_complete
    assert not shutdown_complete

    handler = Bonnette(app)

    assert startup_complete
    assert not shutdown_complete

    response = handler(request)

    assert response.status_code == 200
    assert dict(response.headers) == {
        "content-length": "35",
        "content-type": "text/html; charset=utf-8",
    }
    assert response.get_body() == b"<html><h1>Hello, world!</h1></html>"
    assert response.charset == "utf-8"
    assert response.mimetype == "text/html"
    assert startup_complete
    assert shutdown_complete
