import typing

import pytest


class MockHttpRequest:
    def __init__(
        self,
        method: str = "GET",
        url: str = "/",
        headers: typing.Optional[typing.Mapping[str, str]] = {
            "content-type": "text/html; charset=utf-8"
        },
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


@pytest.fixture
def mock_http_request() -> MockHttpRequest:
    return MockHttpRequest
