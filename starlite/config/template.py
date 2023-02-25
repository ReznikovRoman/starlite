from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from inspect import isclass
from typing import Callable, Generic, TypeVar, cast

from starlite.exceptions import ImproperlyConfiguredException
from starlite.template import TemplateEngineProtocol
from starlite.types import PathType

T = TypeVar("T", bound=TemplateEngineProtocol)


@dataclass
class TemplateConfig(Generic[T]):
    """Configuration for Templating.

    To enable templating, pass an instance of this class to the :class:`Starlite <starlite.app.Starlite>` constructor using the
    'template_config' key.
    """

    engine: type[T] | T
    """A template engine adhering to the :class:`TemplateEngineProtocol <starlite.template.base.TemplateEngineProtocol>`."""
    directory: PathType | list[PathType] | None = field(default=None)
    """A directory or list of directories from which to serve templates."""
    engine_callback: Callable[[T], None] | None = field(default=None)
    """A callback function that allows modifying the instantiated templating protocol."""

    def __post_init__(self) -> None:
        """Ensure that directory is set if engine is a class."""
        if isclass(self.engine) and not self.directory:
            raise ImproperlyConfiguredException("directory is a required kwarg when passing a template engine class")

    def to_engine(self) -> T:
        """Instantiate the template engine."""
        template_engine = cast("T", self.engine(self.directory) if isclass(self.engine) else self.engine)
        if callable(self.engine_callback):
            self.engine_callback(template_engine)  # pylint: disable=E1102
        return template_engine

    @cached_property
    def engine_instance(self) -> T:
        """Return the template engine instance."""
        return self.to_engine()
