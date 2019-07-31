import urllib.parse
import asyncio
import enum
import cgi
import logging
import typing

from azure.functions import HttpRequest, HttpResponse


def get_logger() -> logging.Logger:
    logging.basicConfig(
        format="[%(asctime)s] %(message)s",
        level=logging.INFO,
        datefmt="%d-%b-%y %H:%M:%S",
    )
    logger = logging.getLogger("bonnette")
    logger.setLevel(logging.INFO)
    return logger


class ASGICycleState(enum.Enum):
    REQUEST = enum.auto()
    RESPONSE = enum.auto()


class ASGICycle:
    def __init__(self, scope: dict, spec_version: int) -> None:
        """
        Handle ASGI application request-response cycle for Azure Functions.
        """
        self.scope = scope
        self.body = b""
        self.spec_version = spec_version
        self.state = ASGICycleState.REQUEST
        self.app_queue = None
        self.response = {}
        self.charset = None
        self.mimetype = None

    def __call__(self, app, body: bytes) -> dict:
        """
        Receives the application and any body included in the request, then builds the
        ASGI instance using the connection scope.
        """
        loop = asyncio.new_event_loop()
        self.app_queue = asyncio.Queue(loop=loop)
        self.put_message({"type": "http.request", "body": body, "more_body": False})

        if self.spec_version == 3:
            asgi_instance = app(self.scope, self.receive, self.send)
        else:
            asgi_instance = app(self.scope)(self.receive, self.send)

        asgi_task = loop.create_task(asgi_instance)
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
            if message_type != "http.response.start":
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

            self.on_request(headers, status_code)
            self.state = ASGICycleState.RESPONSE

        elif self.state is ASGICycleState.RESPONSE:
            if message_type != "http.response.body":
                raise RuntimeError(
                    f"Expected 'http.response.body', received: {message_type}"
                )

            body = message.get("body", b"")
            more_body = message.get("more_body", False)

            # The body must be completely read before returning the response.
            self.body += body

            if not more_body:
                self.on_response()
                self.put_message({"type": "http.disconnect"})

    def on_request(self, headers: dict, status_code: int) -> None:
        self.response["status_code"] = status_code
        self.response["headers"] = {k.decode(): v.decode() for k, v in headers.items()}
        self.response["mimetype"] = self.mimetype
        self.response["charset"] = self.charset

    def on_response(self) -> None:
        self.response["body"] = self.body


class Lifespan:
    def __init__(self, app: typing.Any, logger: logging.Logger) -> None:
        self.app = app
        self.logger = logger
        self.startup_event: asyncio.Event = asyncio.Event()
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.app_queue: asyncio.Queue = asyncio.Queue()

    async def run(self):
        try:
            await self.app({"type": "lifespan"}, self.receive, self.send)
        except BaseException as exc:  # pragma: no cover
            self.logger.error(f"Exception in 'lifespan' protocol: {exc}")
        finally:
            self.startup_event.set()
            self.shutdown_event.set()

    async def send(self, message: dict) -> None:
        if message["type"] == "lifespan.startup.complete":
            self.startup_event.set()
        elif message["type"] == "lifespan.shutdown.complete":
            self.shutdown_event.set()
        else:  # pragma: no cover
            raise RuntimeError(
                f"Expected lifespan message type, received: {message['type']}"
            )

    async def receive(self) -> dict:
        message = await self.app_queue.get()
        return message

    async def wait_startup(self):
        self.logger.info("Waiting for application startup.")
        await self.app_queue.put({"type": "lifespan.startup"})
        await self.startup_event.wait()

    async def wait_shutdown(self):
        self.logger.info("Waiting for application shutdown.")
        await self.app_queue.put({"type": "lifespan.shutdown"})
        await self.shutdown_event.wait()


class Bonnette:
    def __init__(
        self,
        app,
        debug: bool = False,
        spec_version: int = 3,
        enable_lifespan: bool = True,
    ) -> None:
        self.app = app
        self.debug = debug
        self.spec_version = spec_version
        self.enable_lifespan = enable_lifespan
        self.logger = get_logger()

        if self.enable_lifespan:
            loop = asyncio.get_event_loop()
            self.lifespan = Lifespan(self.app, logger=self.logger)
            loop.create_task(self.lifespan.run())
            loop.run_until_complete(self.lifespan.wait_startup())

    def __call__(self, event: HttpRequest) -> HttpResponse:
        try:
            response = self.handler(event)
        except BaseException as exc:  # pragma: no cover
            raise exc
        else:
            return response

    def handler(self, event: HttpRequest) -> HttpResponse:
        parsed_url = urllib.parse.urlparse(event.url)
        query_string = (
            urllib.parse.urlencode(event.params).encode() if event.params else b""
        )
        scope = {
            "type": "http",
            "server": None,
            "client": None,
            "method": event.method,
            "raw_path": None,
            "path": parsed_url.path,
            "scheme": parsed_url.scheme,
            "http_version": "1.1",
            "query_string": query_string,
            "headers": [[k.encode(), v.encode()] for k, v in event.headers.items()],
        }
        body = event.get_body() or b""
        asgi_cycle = ASGICycle(scope, spec_version=self.spec_version)
        response = asgi_cycle(self.app, body=body)

        if self.enable_lifespan:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.lifespan.wait_shutdown())

        return HttpResponse(
            body=response["body"],
            headers=response["headers"],
            status_code=response["status_code"],
            mimetype=response["mimetype"],
            charset=response["charset"],
        )
