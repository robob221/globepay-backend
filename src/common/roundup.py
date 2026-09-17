import math
from decimal import Decimal


def compute_roundup(amount: Decimal, denomination: Decimal) -> Decimal:
    """How much extra is needed to bring `amount` up to the next multiple of
    `denomination`. Returns 0 if already exactly on a multiple."""
    if denomination <= 0:
        return Decimal("0.00")
    multiples = math.ceil(amount / denomination)
    rounded = Decimal(multiples) * denomination
    return (rounded - amount).quantize(Decimal("0.01"))
