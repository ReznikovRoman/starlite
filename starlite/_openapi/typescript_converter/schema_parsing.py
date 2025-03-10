import re
from typing import Any, Dict, Literal, Optional, Set, Union, cast, overload, TYPE_CHECKING

from pydantic_openapi_schema.v3_1_0 import Schema

from starlite._openapi.enums import OpenAPIType
from starlite._openapi.typescript_converter.types import (
    TypeScriptAnonymousInterface,
    TypeScriptArray,
    TypeScriptElement,
    TypeScriptInterface,
    TypeScriptIntersection,
    TypeScriptLiteral,
    TypeScriptPrimitive,
    TypeScriptProperty,
    TypeScriptUnion,
)

__all__ = ("create_interface", "is_schema_value", "normalize_typescript_namespace", "parse_schema", "parse_type_schema")

if TYPE_CHECKING:
    from typing_extensions import TypeGuard

openapi_typescript_equivalent_types = Literal[
    "string", "boolean", "number", "null", "Record<string, unknown>", "unknown[]"
]

openapi_to_typescript_type_map: Dict[OpenAPIType, openapi_typescript_equivalent_types] = {
    OpenAPIType.ARRAY: "unknown[]",
    OpenAPIType.BOOLEAN: "boolean",
    OpenAPIType.INTEGER: "number",
    OpenAPIType.NULL: "null",
    OpenAPIType.NUMBER: "number",
    OpenAPIType.OBJECT: "Record<string, unknown>",
    OpenAPIType.STRING: "string",
}

invalid_namespace_re = re.compile(r"[^\w+_$]*")
allowed_key_re = re.compile(r"[\w+_$]*")


def normalize_typescript_namespace(value: str, allow_quoted: bool) -> str:
    """Normalize a namespace, e.g. variable name, or object key, to values supported by TS.

    Args:
        value: A string to normalize.
        allow_quoted: Whether to allow quoting the value.

    Returns:
        A normalized value
    """
    if not allow_quoted and not (value[0].isalpha() or value[0] in {"_", "$"}):
        raise ValueError(f"invalid typescript namespace {value}")
    if allow_quoted:
        if allowed_key_re.fullmatch(value):
            return value
        return f'"{value}"'
    return invalid_namespace_re.sub("", value)


def is_schema_value(value: Any) -> "TypeGuard[Schema]":
    """Typeguard for a schema value.

    Args:
        value: An arbitrary value

    Returns:
        A typeguard boolean dictating whether the passed in value is a Schema.
    """
    return isinstance(value, Schema)


@overload
def create_interface(properties: Dict[str, Schema], required: Optional[Set[str]]) -> TypeScriptAnonymousInterface:
    ...


@overload
def create_interface(properties: Dict[str, Schema], required: Optional[Set[str]], name: str) -> TypeScriptInterface:
    ...


def create_interface(
    properties: Dict[str, Schema], required: Optional[Set[str]] = None, name: Optional[str] = None
) -> Union[TypeScriptAnonymousInterface, TypeScriptInterface]:
    """Create a typescript interface from the given schema.properties values.

    Args:
        properties: schema.properties mapping.
        required: An optional list of required properties.
        name: An optional string representing the interface name.

    Returns:
        A typescript interface or anonymous interface.
    """
    parsed_properties = tuple(
        TypeScriptProperty(
            key=normalize_typescript_namespace(key, allow_quoted=True),
            value=parse_schema(schema),
            required=key in required if required is not None else True,
        )
        for key, schema in properties.items()
    )
    return (
        TypeScriptInterface(name=name, properties=parsed_properties)
        if name is not None
        else TypeScriptAnonymousInterface(properties=parsed_properties)
    )


def parse_type_schema(schema: Schema) -> Union[TypeScriptPrimitive, TypeScriptLiteral, TypeScriptUnion]:
    """Parse an OpenAPI schema representing a primitive type(s).

    Args:
        schema: An OpenAPI schema.

    Returns:
        A typescript type.
    """
    if schema.enum:
        return TypeScriptUnion(types=tuple(TypeScriptLiteral(value=value) for value in schema.enum))
    if schema.const:
        return TypeScriptLiteral(value=schema.const)
    if isinstance(schema.type, list):
        return TypeScriptUnion(
            tuple(
                TypeScriptPrimitive(openapi_to_typescript_type_map[cast("OpenAPIType", s_type)])
                for s_type in schema.type
            )
        )
    if schema.type in openapi_to_typescript_type_map:
        return TypeScriptPrimitive(openapi_to_typescript_type_map[cast("OpenAPIType", schema.type)])
    raise TypeError(f"received an unexpected openapi type: {schema.type}")  # pragma: no cover


def parse_schema(schema: Schema) -> TypeScriptElement:
    """Parse an OpenAPI schema object recursively to create typescript types.

    Args:
        schema: An OpenAPI Schema object.

    Returns:
        A typescript type.
    """
    if schema.allOf:
        return TypeScriptIntersection(tuple(parse_schema(s) for s in schema.allOf if is_schema_value(s)))
    if schema.oneOf:
        return TypeScriptUnion(tuple(parse_schema(s) for s in schema.oneOf if is_schema_value(s)))
    if is_schema_value(schema.items):
        return TypeScriptArray(parse_schema(schema.items))
    if schema.type == OpenAPIType.OBJECT:
        return create_interface(
            properties={k: v for k, v in schema.properties.items() if is_schema_value(v)} if schema.properties else {},
            required=set(schema.required) if schema.required else None,
        )
    return parse_type_schema(schema=schema)
