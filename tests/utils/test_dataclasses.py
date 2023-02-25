from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from starlite.utils.dataclasses import DataclassSerializerMixin
from tests import Pet, PetFactory

pet = PetFactory.build()


@dataclass
class Person(DataclassSerializerMixin):
    first_name: str
    last_name: str
    id: str
    optional: Optional[str]
    complex: Dict[str, List[Dict[str, str]]]
    pets: Optional[List[Pet]] = None


@pytest.fixture
def person_dataclass() -> Person:
    return Person(
        first_name="Moishe",
        last_name="Zuchmir",
        id="1",
        optional=None,
        complex={"key": [{"complex": "value"}]},
        pets=[pet],
    )


@pytest.mark.parametrize(
    "exclude_none, exclude, expected",
    [
        (
            False,
            None,
            [
                ("first_name", "Moishe"),
                ("last_name", "Zuchmir"),
                ("id", "1"),
                ("optional", None),
                ("complex", {"key": [{"complex": "value"}]}),
                ("pets", [pet]),
            ],
        ),
        (
            True,
            None,
            [
                ("first_name", "Moishe"),
                ("last_name", "Zuchmir"),
                ("id", "1"),
                ("complex", {"key": [{"complex": "value"}]}),
                ("pets", [pet]),
            ],
        ),
        (
            False,
            {"complex", "pets"},
            [
                ("first_name", "Moishe"),
                ("last_name", "Zuchmir"),
                ("id", "1"),
                ("optional", None),
            ],
        ),
        (
            True,
            {"optional"},
            [
                ("first_name", "Moishe"),
                ("last_name", "Zuchmir"),
                ("id", "1"),
                ("complex", {"key": [{"complex": "value"}]}),
                ("pets", [pet]),
            ],
        ),
        (
            True,
            {"first_name", "last_name", "id", "optional", "complex", "pets"},
            [],
        ),
    ],
)
def test_serialization(
    exclude_none: bool,
    exclude: set[str] | None,
    expected: list[tuple[str, Any]],
    person_dataclass: Person,
) -> None:
    serialized = person_dataclass.dict(exclude_none=exclude_none, exclude=exclude)
    assert isinstance(serialized, dict)
    assert [(key, value) for key, value in serialized.items()] == expected
