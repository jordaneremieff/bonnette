import urllib.parse
import asyncio
import enum
import cgi
from typing import Any
from azure.functions import HttpRequest, HttpResponse


class ASGICycleState(enum.Enum):
    REQUEST = enum.auto()
    RESPONSE = enum.auto()


class ASGICycle:
    def __init__(self, scope: dict, **kwargs) -> None:
        """
        Handle ASGI application request-response cycle for Azure Functions.
        """
        self.scope = scope
        self.body = b""
        self.state = ASGICycleState.REQUEST
        self.app_queue = None
        self.response = {}
        self.charset = None
        self.mimetype = None

    def __call__(self, app, body: bytes = b"") -> dict:
        """
        Run the event loop and instantiate the ASGI application for the current request.
        """
        loop = asyncio.new_event_loop()
        self.app_queue = asyncio.Queue(loop=loop)
        self.put_message({"type": "http.request", "body": body, "more_body": False})
        asgi_instance = app(self.scope)
        asgi_task = loop.create_task(asgi_instance(self.receive, self.send))
        loop.run_until_complete(asgi_task)
        return self.response

    def put_message(self, message: dict) -> None:
        self.app_queue.put_nowait(message)

    async def receive(self) -> dict:
        message = await self.app_queue.get()
        return message

    async def send(self, message: dict) -> None:
        message_type = message["type"]

        if self.state is ASGICycleState.REQUEST:
            if message_type != "http.response.start":  # pragma: no cover
                raise RuntimeError(
                    f"Expected 'http.response.start', received: {message_type}"
                )

            status_code = message["status"]
            headers = {k: v for k, v in message.get("headers", [])}

            if b"content-type" in headers:
                mimetype, options = cgi.parse_header(headers[b"content-type"].decode())
                charset = options.get("charset", None)
                if charset:
                    self.charset = charset
                if mimetype:
                    self.mimetype = mimetype

            self.on_response_start(headers, status_code)
            self.state = ASGICycleState.RESPONSE

        elif self.state is ASGICycleState.RESPONSE:
            if message_type != "http.response.body":  # pragma: no cover
                raise RuntimeError(
                    f"Expected 'http.response.body', received: {message_type}"
                )

            body = message.get("body", b"")
            more_body = message.get("more_body", False)

            self.body += body

            if not more_body:
                self.on_response_close()
                self.put_message({"type": "http.disconnect"})

    def on_response_start(self, headers: dict, status_code: int) -> None:
        self.response["status_code"] = status_code
        self.response["headers"] = {k.decode(): v.decode() for k, v in headers.items()}
        self.response["mimetype"] = self.mimetype
        self.response["charset"] = self.charset

    def on_response_close(self) -> None:
        self.response["body"] = self.body


class Bonnette:
    """
    A adapter that wraps an ASGI application and handles Azure Functions requests.

    After building the connection scope, it runs the ASGI application cycle and then
    serializes the response into an `HttpResponse`.
    """

    def __init__(self, app, debug: bool = False) -> None:
        self.app = app
        self.debug = debug

    def __call__(self, *args, **kwargs) -> Any:
        """
        Attempt to run the application request-response cycle.

        # TODO: Debug responses
        """
        try:
            response = self.asgi(*args, **kwargs)
        except Exception as exc:  # pragma: no cover
            raise exc
        else:
            return response

    def asgi(self, event: HttpRequest) -> dict:
        server = None
        client = None
        scheme = "https"
        method = event.method
        headers = event.headers.items()
        parsed = urllib.parse.urlparse(event.url)
        scheme = parsed.scheme
        path = parsed.path
        query_string = (
            urllib.parse.urlencode(event.params).encode() if event.params else b""
        )
        scope = {
            "type": "http",
            "server": server,
            "client": client,
            "method": method,
            "path": path,
            "scheme": scheme,
            "http_version": "1.1",
            "root_path": "",
            "query_string": query_string,
            "headers": [[k.encode(), v.encode()] for k, v in headers],
        }
        body = event.get_body() or b""
        response = ASGICycle(scope)(self.app, body=body)
        return HttpResponse(
            body=response["body"],
            headers=response["headers"],
            status_code=response["status_code"],
            mimetype=response["mimetype"],
            charset=response["charset"],
        )
