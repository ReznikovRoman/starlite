from typing import Any, Dict, Tuple
from urllib.parse import urlencode

import pytest

from starlite import HttpMethod
from starlite._parsers import (
    _parse_headers,
    parse_cookie_string,
    parse_headers,
    parse_query_string,
    parse_url_encoded_form_data,
)
from starlite.datastructures import Cookie, MultiDict
from starlite.testing import RequestFactory, create_test_client


def test_parse_form_data() -> None:
    result = parse_url_encoded_form_data(
        encoded_data=urlencode(
            [
                ("value", "10"),
                ("value", "12"),
                ("veggies", '["tomato", "potato", "aubergine"]'),
                ("nested", '{"some_key": "some_value"}'),
                ("calories", "122.53"),
                ("healthy", "true"),
                ("polluting", "false"),
            ]
        ).encode(),
    )
    assert result == {
        "value": [10, 12],
        "veggies": ["tomato", "potato", "aubergine"],
        "nested": {"some_key": "some_value"},
        "calories": 122.53,
        "healthy": True,
        "polluting": False,
    }


def test_parse_utf8_form_data() -> None:
    result = parse_url_encoded_form_data(
        encoded_data=urlencode(
            [
                ("value", "äüß"),
            ]
        ).encode(),
    )
    assert result == {"value": "äüß"}


@pytest.mark.parametrize(
    "cookie_string, expected",
    (
        ("ABC    = 123;   efg  =   456", {"ABC": "123", "efg": "456"}),
        ("foo= ; bar=", {"foo": "", "bar": ""}),
        ('foo="bar=123456789&name=moisheZuchmir"', {"foo": "bar=123456789&name=moisheZuchmir"}),
        ("email=%20%22%2c%3b%2f", {"email": ' ",;/'}),
        ("foo=%1;bar=bar", {"foo": "%1", "bar": "bar"}),
        ("foo=bar;fizz  ; buzz", {"": "buzz", "foo": "bar"}),
        ("  fizz; foo=  bar", {"": "fizz", "foo": "bar"}),
        ("foo=false;bar=bar;foo=true", {"bar": "bar", "foo": "true"}),
        ("foo=;bar=bar;foo=boo", {"bar": "bar", "foo": "boo"}),
        (
            Cookie(key="abc", value="123", path="/head", domain="localhost").to_header(header=""),
            {"Domain": "localhost", "Path": "/head", "SameSite": "lax", "abc": "123"},
        ),
    ),
)
def test_parse_cookie_string(cookie_string: str, expected: Dict[str, str]) -> None:
    assert parse_cookie_string(cookie_string) == expected


def test_parse_query_string() -> None:
    query: Dict[str, Any] = {
        "value": "10",
        "veggies": ["tomato", "potato", "aubergine"],
        "calories": "122.53",
        "healthy": True,
        "polluting": False,
    }
    request = RequestFactory().get(query_params=query)
    result = MultiDict(parse_query_string(request.scope.get("query_string", b"")))

    assert result.dict() == {
        "value": ["10"],
        "veggies": ["tomato", "potato", "aubergine"],
        "calories": ["122.53"],
        "healthy": [True],
        "polluting": [False],
    }


@pytest.mark.parametrize(
    "values",
    (
        (("first", "x@test.com"), ("second", "aaa")),
        (("first", "&@A.ac"), ("second", "aaa")),
        (("first", "a@A.ac&"), ("second", "aaa")),
        (("first", "a@A&.ac"), ("second", "aaa")),
    ),
)
def test_query_parsing_of_escaped_values(values: Tuple[Tuple[str, str], Tuple[str, str]]) -> None:
    # https://github.com/starlite-api/starlite/issues/915
    with create_test_client([]) as client:
        request = client.build_request(method=HttpMethod.GET, url="http://www.example.com", params=dict(values))
        parsed_query = parse_query_string(request.url.query)
        assert parsed_query == values


def test_parse_headers() -> None:
    """Test that headers are parsed correctly."""
    headers = [
        [b"Host", b"localhost:8000"],
        [b"User-Agent", b"curl/7.64.1"],
        [b"Accept", b"*/*"],
        [b"Cookie", b"foo=bar; bar=baz"],
        [b"Content-Type", b"application/x-www-form-urlencoded"],
        [b"Content-Length", b"12"],
    ]
    parsed = parse_headers(headers)
    assert parsed["Host"] == "localhost:8000"
    assert parsed["User-Agent"] == "curl/7.64.1"
    assert parsed["Accept"] == "*/*"
    assert parsed["Cookie"] == "foo=bar; bar=baz"
    assert parsed["Content-Type"] == "application/x-www-form-urlencoded"
    assert parsed["Content-Length"] == "12"
    # demonstrate that calling the private function with lists (as ASGI specifies)
    # does raise an error
    with pytest.raises(TypeError):
        _parse_headers(headers)  # type: ignore[arg-type]
