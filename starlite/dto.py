from dataclasses import asdict
from inspect import isawaitable
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from pydantic import BaseConfig, BaseModel, create_model
from pydantic.fields import SHAPE_SINGLETON, ModelField, Undefined
from pydantic.generics import GenericModel
from pydantic_factories import ModelFactory

from starlite.exceptions import ImproperlyConfiguredException
from starlite.plugins import SerializationPluginProtocol, get_plugin_for_value
from starlite.utils import (
    convert_dataclass_to_model,
    convert_typeddict_to_model,
    is_async_callable,
    is_dataclass_class_or_instance,
    is_typed_dict,
)

__all__ = ("DTO", "DTOFactory")


if TYPE_CHECKING:
    from typing import Awaitable


def get_field_type(model_field: ModelField) -> Any:
    """Given a model field instance, return the correct type.

    Args:
        model_field (ModelField): `pydantic.fields.ModelField`

    Returns:
        Type of field.
    """
    outer_type = model_field.outer_type_
    inner_type = model_field.type_
    if "ForwardRef" not in repr(outer_type):
        return outer_type
    if model_field.shape == SHAPE_SINGLETON:
        return inner_type
    # This might be too simplistic
    return List[inner_type]  # type: ignore


T = TypeVar("T")


class DTO(GenericModel, Generic[T]):
    """Data Transfer Object."""

    class Config(BaseConfig):
        arbitrary_types_allowed = True
        orm_mode = True

    dto_source_model: ClassVar[Any]
    dto_field_mapping: ClassVar[Dict[str, str]]
    dto_source_plugin: ClassVar[Optional[SerializationPluginProtocol]] = None

    @classmethod
    def _from_value_mapping(cls, mapping: Dict[str, Any]) -> "DTO[T]":
        for dto_key, original_key in cls.dto_field_mapping.items():
            value = mapping.pop(original_key)
            mapping[dto_key] = value
        return cls(**mapping)

    @classmethod
    def from_model_instance(cls, model_instance: T) -> "DTO[T]":
        """Given an instance of the source model, create an instance of the given DTO subclass.

        Args:
            model_instance (T): instance of source model.

        Returns:
            Instance of the :class:`DTO` subclass.
        """
        if cls.dto_source_plugin is not None and cls.dto_source_plugin.is_plugin_supported_type(model_instance):
            result = cls.dto_source_plugin.to_dict(model_instance=model_instance)
            if isawaitable(result):
                raise ImproperlyConfiguredException(
                    f"plugin {type(cls.dto_source_plugin).__name__} to_dict method is async. "
                    f"Use 'DTO.from_model_instance_async instead'",
                )
            values = cast("Dict[str, Any]", result)
        elif isinstance(model_instance, BaseModel):
            values = model_instance.dict()
        elif isinstance(model_instance, dict):
            values = dict(model_instance)  # copy required as `_from_value_mapping()`` mutates ``values`.
        else:
            values = asdict(model_instance)  # type:ignore[call-overload]
        return cls._from_value_mapping(mapping=values)

    @classmethod
    async def from_model_instance_async(cls, model_instance: T) -> "DTO[T]":
        """Given an instance of the source model, create an instance of the given DTO subclass asynchronously.

        Args:
            model_instance (T): instance of source model.

        Returns:
            Instance of the :class:`DTO` subclass.
        """
        if (
            cls.dto_source_plugin is not None
            and cls.dto_source_plugin.is_plugin_supported_type(model_instance)
            and is_async_callable(cls.dto_source_plugin.to_dict)
        ):
            values = await cast(
                "Awaitable[Dict[str, Any]]", cls.dto_source_plugin.to_dict(model_instance=model_instance)
            )
            return cls._from_value_mapping(mapping=values)
        return cls.from_model_instance(model_instance=model_instance)

    def to_model_instance(self) -> T:
        """Convert the DTO instance into an instance of the original class from which the DTO was created.

        Returns:
            Instance of source model type.
        """
        values = self.dict()

        for dto_key, original_key in self.dto_field_mapping.items():
            value = values.pop(dto_key)
            values[original_key] = value

        if self.dto_source_plugin is not None and self.dto_source_plugin.is_plugin_supported_type(
            self.dto_source_model
        ):
            return cast("T", self.dto_source_plugin.from_dict(model_class=self.dto_source_model, **values))

        # we are dealing with a pydantic model or dataclass
        return cast("T", self.dto_source_model(**values))


class DTOFactory:
    """Create :class:`DTO` type.

    Pydantic models, :class:`TypedDict <typing.TypedDict>` and dataclasses are natively supported. Other types supported
    via plugins.
    """

    def __init__(self, plugins: Optional[List[SerializationPluginProtocol]] = None) -> None:
        """Initialize ``DTOFactory``

        Args:
            plugins: Plugins used to support ``DTO`` construction from arbitrary types.
        """
        self.plugins = plugins or []

    def __call__(
        self,
        name: str,
        source: Type[T],
        exclude: Optional[List[str]] = None,
        field_mapping: Optional[Dict[str, Union[str, Tuple[str, Any]]]] = None,
        field_definitions: Optional[Dict[str, Tuple[Any, Any]]] = None,
        base: Type[DTO] = DTO,
    ) -> Type[DTO[T]]:
        """Given a supported model class - either pydantic, :class:`TypedDict <typing.TypedDict>`, dataclass or a class supported
        via plugins, create a DTO pydantic model class.

        An instance of the factory must first be created, passing any plugins to it.
        It can then be used to create a DTO by calling the instance like a function. Additionally, it can exclude (drop)
        attributes specifies in the 'exclude' list and remap field names and/or field types.

        For example, given a pydantic model

        .. code-block: python

            class MyClass(BaseModel):
                first: int
                second: int

            MyClassDTO = DTOFactory()(
                MyClass, exclude=["first"], field_mapping={"second": ("third", float)}
            )

        ``MyClassDTO`` is now equal to this:

        .. code-block: python

            class MyClassDTO(BaseModel):
                third: float

        It can be used as a regular pydantic model:

        .. code-block: python

            @post(path="/my-path")
            def create_obj(data: MyClassDTO) -> MyClass:
                ...

        This will affect parsing, validation and how OpenAPI schema is generated exactly like when using a pydantic model.

        Note: Although the value generated is a pydantic factory, because it is being generated programmatically,
        it's currently not possible to extend editor auto-complete for the DTO properties - it will be typed as a
        Pydantic BaseModel, but no attributes will be inferred in the editor.

        Args:
            name (str): This becomes the name of the generated pydantic model.
            source (type[T]): A type that is either a subclass of ``BaseModel``, :class:`TypedDict <typing.TypedDict>`,
                a ``dataclass`` or any other type with a plugin registered.
            exclude (list[str] | None): Names of attributes on ``source``. Named Attributes will not have a field
                generated on the resultant pydantic model.
            field_mapping (dict[str, str | tuple[str, Any]] | None): Keys are names of attributes on ``source``. Values
                are either a ``str`` to rename an attribute, or tuple `(str, Any)` to remap both name and type of the
                attribute.
            field_definitions (dict[str, tuple[Any, Any]] | None): Add fields to the model that don't exist on ``source``.
                These are passed as kwargs to `pydantic.create_model()`.
            base (type[DTO] | None): Base class for the generated pydantic model.

        Returns:
            Type[DTO[T]]

        Raises:
            ImproperlyConfiguredException: If ``source`` is not a pydantic model, :class:`TypedDict <typing.TypedDict>`
                or dataclass, and there is no plugin registered for its type.
        """
        field_definitions = field_definitions or {}
        exclude = exclude or []
        field_mapping = field_mapping or {}
        fields, plugin = self._get_fields_from_source(source)
        field_definitions = self._populate_field_definitions(exclude, field_definitions, field_mapping, fields)
        dto = cast(
            "Type[DTO[T]]", create_model(name, __base__=base, **field_definitions)  # type:ignore[call-overload]
        )
        dto.dto_source_model = source
        dto.dto_source_plugin = plugin
        dto.dto_field_mapping = {}
        for key, value_tuple in field_mapping.items():
            if isinstance(value_tuple, tuple):
                value = value_tuple[0]
            elif isinstance(value_tuple, str):
                value = value_tuple
            else:
                raise TypeError(f"Expected a string or tuple containing a string, but got {value_tuple!r}")
            dto.dto_field_mapping[value] = key
        return dto

    def _get_fields_from_source(
        self, source: Type[T]  # pyright: ignore
    ) -> Tuple[Dict[str, ModelField], Optional[SerializationPluginProtocol]]:
        """Convert a ``BaseModel`` subclass, :class:`TypedDict <typing.TypedDict>`, ``dataclass`` or any other type that
        has a plugin registered into a mapping of :class:`str` to ``ModelField``.
        """
        fields: Optional[Dict[str, ModelField]] = None
        if plugin := get_plugin_for_value(value=source, plugins=self.plugins):
            model = plugin.to_data_container_class(model_class=source)
            fields = model.__fields__

            return fields, plugin  # type: ignore

        if issubclass(source, BaseModel):
            source.update_forward_refs()
            fields = source.__fields__
        elif is_dataclass_class_or_instance(source):
            fields = convert_dataclass_to_model(source).__fields__
        elif is_typed_dict(source):
            fields = convert_typeddict_to_model(source).__fields__

        if fields:
            return fields, plugin

        raise ImproperlyConfiguredException(f"No supported plugin found for value {source} - cannot create value")

    def _populate_field_definitions(
        self,
        exclude: List[str],
        field_definitions: Dict[str, Tuple[Any, Any]],
        field_mapping: Dict[str, Union[str, Tuple[str, Any]]],
        fields: Dict[str, ModelField],
    ) -> Dict[str, Tuple[Any, Any]]:
        """Populate ``field_definitions``, ignoring fields in ``exclude``, and remapping fields in ``field_mapping``."""
        for field_name, model_field in fields.items():
            if field_name in exclude:
                continue
            field_type = get_field_type(model_field=model_field)
            self._populate_single_field_definition(
                field_definitions, field_mapping, field_name, field_type, model_field
            )
        return field_definitions

    @classmethod
    def _populate_single_field_definition(
        cls,
        field_definitions: Dict[str, Tuple[Any, Any]],
        field_mapping: Dict[str, Union[str, Tuple[str, Any]]],
        field_name: str,
        field_type: Any,
        model_field: ModelField,
    ) -> None:
        if field_name in field_mapping:
            field_name, field_type = cls._remap_field(field_mapping, field_name, field_type)
            if ModelFactory.is_constrained_field(field_type):
                field_definitions[field_name] = (field_type, ...)
            elif model_field.field_info.default not in (Undefined, None, ...):
                field_definitions[field_name] = (field_type, model_field.default)
            elif model_field.required or not model_field.allow_none:
                field_definitions[field_name] = (field_type, ...)
            else:
                field_definitions[field_name] = (field_type, None)
        else:
            # prevents losing Optional
            field_type = Optional[field_type] if model_field.allow_none else field_type
            if ModelFactory.is_constrained_field(field_type):
                field_definitions[field_name] = (field_type, ...)
            else:
                field_definitions[field_name] = (field_type, model_field.field_info)

    @staticmethod
    def _remap_field(
        field_mapping: Dict[str, Union[str, Tuple[str, Any]]], field_name: str, field_type: Any
    ) -> Tuple[str, Any]:
        """Return tuple of field name and field type remapped according to entry in ``field_mapping``."""
        mapping = field_mapping[field_name]
        if isinstance(mapping, tuple):
            field_name, field_type = mapping
        else:
            field_name = mapping
        return field_name, field_type
