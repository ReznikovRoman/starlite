from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, cast

from pydantic_openapi_schema.v3_1_0 import (
    Components,
    Contact,
    ExternalDocumentation,
    Info,
    License,
    OpenAPI,
    PathItem,
    Reference,
    SecurityRequirement,
    Server,
    Tag,
)

from starlite._openapi.utils import default_operation_id_creator
from starlite.openapi.controller import OpenAPIController

__all__ = ("OpenAPIConfig",)


if TYPE_CHECKING:
    from starlite.types.callable_types import OperationIDCreator


@dataclass
class OpenAPIConfig:
    """Configuration for OpenAPI.

    To enable OpenAPI schema generation and serving, pass an instance of this class to the
    :class:`Starlite <.app.Starlite>` constructor using the ``openapi_config`` kwargs.
    """

    title: str
    """Title of API documentation."""
    version: str
    """API version, e.g. '1.0.0'."""

    create_examples: bool = field(default=False)
    """Generate examples using the pydantic-factories library."""
    openapi_controller: type[OpenAPIController] = field(default_factory=lambda: OpenAPIController)
    """Controller for generating OpenAPI routes.

    Must be subclass of :class:`OpenAPIController <starlite.openapi.controller.OpenAPIController>`.
    """
    contact: Contact | None = field(default=None)
    """API contact information, should be an :class:`Contact <pydantic_openapi_schema.v3_1_0.contact.Contact>` instance."""
    description: str | None = field(default=None)
    """API description."""
    external_docs: ExternalDocumentation | None = field(default=None)
    """Links to external documentation.

    Should be an instance of :class:`ExternalDocumentation <pydantic_openapi_schema.v3_1_0.external_documentation.ExternalDocumentation>`.
    """
    license: License | None = field(default=None)
    """API Licensing information.

    Should be an instance of :class:`License <pydantic_openapi_schema.v3_1_0.license.License>`.
    """
    security: list[SecurityRequirement] | None = field(default=None)
    """API Security requirements information.

    Should be an instance of
        :data:`SecurityRequirement <pydantic_openapi_schema.v3_1_0.security_requirement.SecurityRequirement>`.
    """
    components: Components | list[Components] | None = field(default=None)
    """API Components information.

    Should be an instance of :class:`Components <pydantic_openapi_schema.v3_1_0.components.Components>` or a list thereof.
    """
    servers: list[Server] = field(default_factory=lambda: [Server(url="/")])
    """A list of :class:`Server <pydantic_openapi_schema.v3_1_0.server.Server>` instances."""
    summary: str | None = field(default=None)
    """A summary text."""
    tags: list[Tag] | None = field(default=None)
    """A list of :class:`Tag <pydantic_openapi_schema.v3_1_0.tag.Tag>` instances."""
    terms_of_service: str | None = field(default=None)
    """URL to page that contains terms of service."""
    use_handler_docstrings: bool = field(default=False)
    """Draw operation description from route handler docstring if not otherwise provided."""
    webhooks: dict[str, PathItem | Reference] | None = field(default=None)
    """A mapping of key to either :class:`PathItem <pydantic_openapi_schema.v3_1_0.path_item.PathItem>` or.

    :class:`Reference <pydantic_openapi_schema.v3_1_0.reference.Reference>` objects.
    """
    root_schema_site: Literal["redoc", "swagger", "elements"] = "redoc"
    """The static schema generator to use for the "root" path of `/schema/`."""
    enabled_endpoints: set[str] = field(
        default_factory=lambda: {"redoc", "swagger", "elements", "openapi.json", "openapi.yaml"}
    )
    """A set of the enabled documentation sites and schema download endpoints."""
    by_alias: bool = True
    """Render pydantic model schema using field aliases, if defined."""
    operation_id_creator: OperationIDCreator = default_operation_id_creator
    """A callable that generates unique operation ids"""

    def to_openapi_schema(self) -> OpenAPI:
        """Return an ``OpenAPI`` instance from the values stored in ``self``.

        Returns:
            An instance of :class:`OpenAPI <pydantic_openapi_schema.v3_1_0.open_api.OpenAPI>`.
        """

        if isinstance(self.components, list):
            merged_components = Components()
            for components in self.components:
                for key in components.__fields__:
                    value = getattr(components, key, None)
                    if value:
                        merged_value_dict = getattr(merged_components, key, {}) or {}
                        merged_value_dict.update(value)
                        setattr(merged_components, key, merged_value_dict)
            self.components = merged_components

        return OpenAPI(
            externalDocs=self.external_docs,
            security=self.security,
            components=cast("Components", self.components),
            servers=self.servers,
            tags=self.tags,
            webhooks=self.webhooks,
            info=Info(
                title=self.title,
                version=self.version,
                description=self.description,
                contact=self.contact,
                license=self.license,
                summary=self.summary,
                termsOfService=self.terms_of_service,  # type: ignore
            ),
            paths={},
        )
