from decimal import Decimal

import pytest

from app.domain.market_math import percentage_change


def test_percentage_change_returns_a_rounded_increase() -> None:
    result = percentage_change(
        Decimal("512.8000"),
        Decimal("506.2500"),
    )

    assert result == Decimal("1.29")


def test_percentage_change_returns_a_signed_decrease() -> None:
    result = percentage_change(
        Decimal("231.4000"),
        Decimal("233.1500"),
    )

    assert result == Decimal("-0.75")


def test_percentage_change_rejects_a_non_positive_reference() -> None:
    with pytest.raises(
        ValueError,
        match="Reference value must be positive",
    ):
        percentage_change(Decimal("10"), Decimal("0"))
