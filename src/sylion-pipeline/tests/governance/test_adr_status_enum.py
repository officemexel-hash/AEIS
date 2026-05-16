from sylion.governance.adr_status_enum import AdrStatusEnum


def test_adr_status_enum_contains_all_members() -> None:
    assert tuple(AdrStatusEnum.__members__) == (
        "PROPOSED",
        "ACCEPTED",
        "REJECTED",
        "SUPERSEDED",
    )


def test_adr_status_enum_values_are_canonical_lowercase() -> None:
    assert tuple(member.value for member in AdrStatusEnum) == (
        "proposed",
        "accepted",
        "rejected",
        "superseded",
    )


def test_adr_status_enum_lookup_by_value() -> None:
    assert AdrStatusEnum("accepted") is AdrStatusEnum.ACCEPTED


def test_adr_status_enum_is_str_subclass() -> None:
    assert isinstance(AdrStatusEnum.REJECTED.value, str)
    assert AdrStatusEnum.REJECTED == "rejected"
