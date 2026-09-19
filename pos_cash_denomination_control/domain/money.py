"""Currency-rounded amount comparison.

Uses `Decimal(str(x))` to avoid binary-float artifacts, mirroring the
semantics of Odoo's `float_compare`/`float_is_zero` without importing `odoo`.
"""

from decimal import ROUND_HALF_UP, Decimal


def compare_amounts(a, b, rounding):
    """Compare two amounts with currency rounding.

    Returns -1, 0, or 1, the same contract as `float_compare`. The
    difference is expressed in units of `rounding` and rounded half-up
    before comparing to zero, so amounts within tolerance compare equal.
    """
    precision = Decimal(str(rounding)) if rounding else Decimal("0.000001")
    diff = Decimal(str(a)) - Decimal(str(b))
    scaled = (diff / precision).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if scaled > 0:
        return 1
    if scaled < 0:
        return -1
    return 0


def is_zero(value, rounding):
    """True when `value` rounds to zero at the given `rounding` precision."""
    return compare_amounts(value, 0, rounding) == 0
