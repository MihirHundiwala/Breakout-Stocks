from decimal import Decimal, ROUND_HALF_UP


PERCENT_QUANTUM = Decimal("0.01")
ONE_HUNDRED = Decimal("100")


def percentage_change(
    current_value: Decimal,
    reference_value: Decimal,
) -> Decimal:
    if reference_value <= 0:
        raise ValueError("Reference value must be positive.")

    return (
        (current_value - reference_value)
        / reference_value
        * ONE_HUNDRED
    ).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)
