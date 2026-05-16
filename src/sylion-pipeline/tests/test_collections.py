from dataclasses import dataclass

from sylion.core.collections import dataclass_to_dict_recursive


@dataclass
class Flat:
    x: int
    y: str


@dataclass
class Child:
    name: str


@dataclass
class Parent:
    child: Child


@dataclass
class Item:
    value: int


class HasToDict:
    def to_dict(self):
        return {"ok": Item(3)}


def test_dataclass_to_dict_recursive_flat():
    assert dataclass_to_dict_recursive(Flat(1, "a")) == {"x": 1, "y": "a"}


def test_dataclass_to_dict_recursive_nested():
    assert dataclass_to_dict_recursive(Parent(Child("n"))) == {"child": {"name": "n"}}


def test_dataclass_to_dict_recursive_list_of_dataclasses():
    assert dataclass_to_dict_recursive({"items": [Item(1), Item(2)]}) == {"items": [{"value": 1}, {"value": 2}]}


def test_dataclass_to_dict_recursive_mixed_types():
    data = {"pair": (Item(1), 2), "custom": HasToDict(), "plain": "x"}
    assert dataclass_to_dict_recursive(data) == {"pair": [{"value": 1}, 2], "custom": {"ok": {"value": 3}}, "plain": "x"}
